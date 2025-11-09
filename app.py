from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta
import os, uuid, hashlib, base64, cv2
import numpy as np
import traceback # Thêm thư viện để in lỗi chi tiết


import config


try:
    import face_recognition
    FACE_LIB = 'face_recognition'
except Exception as e:
    print('face_recognition không khả dụng, sử dụng opencv LBPH:', e)
    FACE_LIB = 'opencv_fallback'


app = Flask(__name__)
CORS(app)
app.secret_key = 'your-secret-key-change-this-in-production'


# ===================================================================
# ✨ TỐI ƯU HÓA TỐC ĐỘ (BƯỚC 1)
# Biến toàn cục để lưu trữ khuôn mặt đã biết (tải 1 lần)
known_face_data = [] # Sẽ lưu (username, encoding)
# ===================================================================




def get_db():
    return mysql.connector.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        autocommit=True
    )


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


# ===================================================================
# ✨ TỐI ƯU HÓA TỐC ĐỘ (BƯỚC 2)
# Hàm này tải TẤT CẢ khuôn mặt từ ổ cứng vào RAM
# ===================================================================
def load_known_faces():
    global known_face_data
    known_face_data = [] # Xóa dữ liệu cũ (nếu tải lại)
    print("Đang tải dữ liệu khuôn mặt đã biết vào bộ nhớ...")
   
    if not os.path.exists(config.FACES_DIR):
        print(f"Thư mục '{config.FACES_DIR}' không tồn tại. Bỏ qua.")
        return


    for fname in os.listdir(config.FACES_DIR):
        if not fname.lower().endswith(('.jpg', '.png', '.jpeg')):
            continue
       
        try:
            # Lấy username từ tên file (ví dụ: 'duyen.jpg' -> 'duyen')
            username = os.path.splitext(fname)[0]
            image_path = os.path.join(config.FACES_DIR, fname)
           
            # Đọc ảnh (dùng cv2 giống code cũ của bạn)
            known_image = cv2.imread(image_path)
           
            if known_image is None:
                print(f"Không thể đọc file: {fname}")
                continue
           
            # Tính encoding (dùng cv2 BGR image)
            encodings = face_recognition.face_encodings(known_image)
           
            if encodings:
                # Lưu (username, encoding) vào RAM
                known_face_data.append((username, encodings[0]))
                print(f"-> Đã tải xong khuôn mặt cho: {username}")
            else:
                print(f"Không tìm thấy khuôn mặt trong: {fname}")
        except Exception as e:
            print(f"Lỗi khi tải {fname}: {e}")
   
    print(f"Đã tải thành công {len(known_face_data)} khuôn mặt vào bộ nhớ.")
# ===================================================================




def detect_station_columns():
    """Detect the station id/name column names used in the `stations` table.
    Returns a tuple (id_col, name_col)."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='stations'", (config.DB_NAME,))
        cols = [r[0] for r in cur.fetchall()]
        cur.close()
        db.close()
        if 'station_id' in cols and 'station_name' in cols:
            return ('station_id', 'station_name')
        if 'id' in cols and 'name' in cols:
            return ('id', 'name')
        if 'station_id' in cols and 'name' in cols:
            return ('station_id', 'name')
        if len(cols) >= 2:
            return (cols[0], cols[1])
    except Exception as e:
        print('detect_station_columns error:', e)
    return ('station_id', 'station_name')




def get_table_columns(table_name):
    """Return a set of column names for the given table in the configured database."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", (config.DB_NAME, table_name))
        cols = set([r[0] for r in cur.fetchall()])
        cur.close()
        db.close()
        return cols
    except Exception as e:
        print(f'get_table_columns({table_name}) error:', e)
        return set()




def get_all_stations():
    """Return list of stations as dicts with keys `station_id` and `station_name` regardless of underlying column names."""
    id_col, name_col = detect_station_columns()
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        # SỬA LỖI DB: Bảng 'stations' của bạn dùng station_id=0 cho tất cả,
        # nên chúng ta dùng TÊN làm ID (value)
        q = f"SELECT {name_col} AS station_id, {name_col} AS station_name FROM stations ORDER BY {name_col}"
        cur.execute(q)
        stations = cur.fetchall()
        return stations
    except Exception as e:
        print('get_all_stations error:', e)
        try:
            cur.execute(f"SELECT station_name AS station_id, station_name FROM stations ORDER BY station_name")
            stations = cur.fetchall()
            return stations
        except Exception as e2:
            print('get_all_stations fallback error:', e2)
            return []
    finally:
        cur.close()
        db.close()




def ensure_stations(station_names):
    """Insert missing station names into stations table. Uses detected name column."""
    id_col, name_col = detect_station_columns()
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(f"SELECT {name_col} FROM stations")
        existing = set([row[0] for row in cur.fetchall()])
        for s in station_names:
            if s not in existing:
                try:
                    cur.execute(f"INSERT INTO stations ({name_col}) VALUES (%s)", (s,))
                except Exception as e:
                    print(f'Unable to insert station {s}:', e)
        db.commit()
    except Exception as e:
        print('ensure_stations error:', e)
    finally:
        cur.close()
        db.close()




def ensure_face_data_table():
    """Create a minimal face_data table if it doesn't exist to avoid runtime errors when uploading faces."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS face_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL UNIQUE,
                face_encoding LONGBLOB,
                photo_path VARCHAR(255),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        ''')
        cols = get_table_columns('users')
        if 'id' in cols:
            try:
                cur.execute('ALTER TABLE face_data ADD CONSTRAINT fk_face_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE')
            except Exception:
                pass
        db.commit()
    except Exception as e:
        print('ensure_face_data_table error:', e)
    finally:
        try:
            cur.close()
            db.close()
        except Exception:
            pass




def ensure_tickets_schema():
    """Ensure tickets table has expected columns. Adds missing columns when possible."""
    try:
        cols = get_table_columns('tickets')
        db = get_db()
        cur = db.cursor()
        alters = []
        want = {
            'user_id': 'INT',
            'ticket_type': 'VARCHAR(50)',
            'purchase_time': 'DATETIME',
            'valid_from': 'DATETIME',
            'valid_to': 'DATETIME',
            'from_station_id': 'INT',
            'to_station_id': 'INT',
            'from_station_name': 'VARCHAR(255)',
            'to_station_name': 'VARCHAR(255)',
            'single_from_station': 'VARCHAR(255)',
            'single_to_station': 'VARCHAR(255)',
            'status': 'VARCHAR(20)',
            'purchase_price': 'INT',
            'used': 'TINYINT(1)',
            'trip_code': 'VARCHAR(100)'
        }
        for k, ddl in want.items():
            if k not in cols:
                alters.append(f"ADD COLUMN {k} {ddl}")
        if alters:
            sql = 'ALTER TABLE tickets ' + ', '.join(alters)
            try:
                cur.execute(sql)
                db.commit()
            except Exception as e:
                print('ensure_tickets_schema ALTER failed:', e)
        cur.close()
        db.close()
    except Exception as e:
        print('ensure_tickets_schema error:', e)




def user_has_active_monthly(user_id):
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM tickets WHERE user_id=%s AND ticket_type='monthly'", (user_id,))
        rows = cur.fetchall()
        cur.close()
        db.close()
        for ex in rows:
            used_flag = ex.get('used') if isinstance(ex, dict) else None
            if used_flag is not None and int(used_flag) == 1:
                continue
            valid_from = ex.get('valid_from') or ex.get('valid_at_datetime') or ex.get('purchase_time')
            valid_to = ex.get('valid_to')
            if valid_to:
                try:
                    vt = valid_to if isinstance(valid_to, datetime) else datetime.fromisoformat(str(valid_to))
                    if vt >= datetime.now():
                        return True
                except Exception:
                    pass
            if valid_from:
                try:
                    vf = valid_from if isinstance(valid_from, datetime) else datetime.fromisoformat(str(valid_from))
                    if (datetime.now() - vf).days < 30:
                        return True
                except Exception:
                    return True
            else:
                return True
        return False
    except Exception as e:
        print('user_has_active_monthly error:', e)
        return False




def user_has_face(user_id):
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute('SELECT 1 FROM face_data WHERE user_id=%s LIMIT 1', (user_id,))
        r = cur.fetchone()
        cur.close()
        db.close()
        return bool(r)
    except Exception as e:
        print('user_has_face error:', e)
        return False


def init_admin():
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE username=%s', ('admin',))
        if not cur.fetchone():
            admin_password = hash_pw('admin123')
            cur.execute(
                'INSERT INTO users (username, email, phone, password, role) VALUES (%s, %s, %s, %s, %s)',
                ('admin', 'admin@metro.local', '0000000000', admin_password, 'admin')
            )
            db.commit()
            print('Tài khoản admin đã được tạo (tên: admin, mật khẩu: admin123)')
        cur.close()
        db.close()
    except Exception as e:
        print(f'Lỗi khởi tạo admin: {e}')


def is_admin():
    if 'user' not in session:
        return False
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT role FROM users WHERE id=%s', (session['user']['id'],))
        user = cur.fetchone()
        return user and user.get('role') == 'admin'
    finally:
        cur.close()
        db.close()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        role = request.form.get('role', 'user')
       
        if not all([username, phone, email, password, password_confirm]):
            return render_template('register.html', error='Vui lòng điền tất cả các trường')
       
        if password != password_confirm:
            return render_template('register.html', error='Mật khẩu không khớp')
       
        if len(password) < 6:
            return render_template('register.html', error='Mật khẩu phải có ít nhất 6 ký tự')
       
        password_hash = hash_pw(password)
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute('INSERT INTO users (username, phone, email, password, role) VALUES (%s, %s, %s, %s, %s)',
                        (username, phone, email, password_hash, role))
            db.commit()
            return redirect(url_for('login'))
        except mysql.connector.Error as e:
            if 'Duplicate entry' in str(e):
                return render_template('register.html', error='Tên đăng nhập hoặc email đã tồn tại')
            return render_template('register.html', error=f'Lỗi đăng ký: {str(e)}')
        finally:
            cur.close()
            db.close()
    return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
       
        if not username or not password:
            return render_template('login.html', error='Vui lòng nhập tên đăng nhập và mật khẩu')
       
        password_hash = hash_pw(password)
        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username, password_hash))
            user = cur.fetchone()
            if user:
                uid = user.get('user_id') if user.get('user_id') is not None else user.get('id')
                session['user'] = {
                    'id': uid,
                    'username': user.get('username') or user.get('name'),
                    'email': user.get('email'),
                    'phone': user.get('phone'),
                    'role': user.get('role', 'user')
                }
                if user.get('role') == 'admin':
                    return redirect(url_for('admin'))
                return redirect(url_for('home'))
            else:
                return render_template('login.html', error='Tên đăng nhập hoặc mật khẩu không đúng')
        except Exception as e:
            return render_template('login.html', error=f'Lỗi đăng nhập: {str(e)}')
        finally:
            cur.close()
            db.close()
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))


@app.route('/api/get_stations', methods=['GET'])
def get_stations_api():
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        stations = get_all_stations()
        return jsonify({'stations': stations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        db.close()


@app.route('/buy_ticket', methods=['GET','POST'])
def buy_ticket():
    if 'user' not in session:
        return redirect(url_for('login'))
    stations = get_all_stations()
    user_id = session['user'].get('id')
    has_active = user_has_active_monthly(user_id)
    has_face = user_has_face(user_id)
   
    if request.method == 'POST':
        user_id = session['user']['id']
        now = datetime.now()
       
        station_from_name = request.form.get('station_from_id')
        station_to_name = request.form.get('station_to_id')
       
        if not station_from_name or not station_to_name:
            return render_template('buy_ticket.html', error='Vui lòng chọn ga đi và ga đến', stations=stations)


        try:
            cdb = get_db()
            ccur = cdb.cursor(dictionary=True)
            check_q = '''
                SELECT * FROM tickets WHERE user_id=%s AND ticket_type='monthly'
            '''
            ccur.execute(check_q, (user_id,))
            existing = ccur.fetchall()
            has_active = False
            for ex in existing:
                used_flag = ex.get('used') if isinstance(ex, dict) else None
                if used_flag is not None and int(used_flag) == 1:
                    continue
                valid_from = ex.get('valid_from') or ex.get('valid_at_datetime') or ex.get('purchase_time')
                valid_to = ex.get('valid_to')
                if valid_to:
                    try:
                        vt = valid_to if isinstance(valid_to, datetime) else datetime.fromisoformat(str(valid_to))
                        if vt >= datetime.now():
                            has_active = True
                            break
                    except Exception:
                        pass
                if valid_from:
                    try:
                        vf = valid_from if isinstance(valid_from, datetime) else datetime.fromisoformat(str(valid_from))
                        if (datetime.now() - vf).days < 30:
                            has_active = True
                            break
                    except Exception:
                        pass
                else:
                    has_active = True
                    break
            ccur.close()
            cdb.close()
            if has_active:
                return render_template('buy_ticket.html', error='Bạn đã có vé tháng đang hoạt động. Mỗi tài khoản chỉ được mua 1 vé tháng.', stations=stations)
        except Exception as e:
            print('Warning checking existing monthly tickets:', e)
       
        db = get_db()
        cur = db.cursor()
        try:
            cols = get_table_columns('tickets')
            insert_cols = ['user_id', 'ticket_type']
            vals = [user_id, 'monthly']


            if 'from_station_name' in cols:
                insert_cols.append('from_station_name')
                vals.append(station_from_name)
            elif 'single_from_station' in cols:
                insert_cols.append('single_from_station')
                vals.append(station_from_name)


            if 'to_station_name' in cols:
                insert_cols.append('to_station_name')
                vals.append(station_to_name)
            elif 'single_to_station' in cols:
                insert_cols.append('single_to_station')
                vals.append(station_to_name)


            now_val = now
            if 'purchase_time' in cols:
                insert_cols.append('purchase_time')
                vals.append(now_val)
            if 'valid_from' in cols:
                insert_cols.append('valid_from')
                vals.append(now_val)
            if 'status' in cols:
                insert_cols.append('status')
                vals.append('NEW')
            if 'purchase_price' in cols:
                insert_cols.append('purchase_price')
                vals.append(500000)
            if 'used' in cols:
                insert_cols.append('used')
                vals.append(0)


            placeholders = ','.join(['%s'] * len(vals))
            q = f"INSERT INTO tickets ({', '.join(insert_cols)}) VALUES ({placeholders})"
            cur.execute(q, tuple(vals))
            db.commit()
           
            if has_face:
                return redirect(url_for('history'))
            else:
                return redirect(url_for('upload_face_page'))
        except Exception as e:
            return render_template('buy_ticket.html', error=f'Lỗi mua vé: {str(e)}', stations=stations)
        finally:
            cur.close()
            db.close()
   
    return render_template('buy_ticket.html', stations=stations, has_active=has_active, has_face=has_face)


@app.route('/upload_face', methods=['GET'])
def upload_face_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('upload_face.html')


@app.route('/api/upload_face', methods=['POST'])
def upload_face():
    if 'user' not in session:
        return jsonify({'error': 'Chưa đăng nhập'}), 403
   
    try:
        file = request.files.get('face')
        if not file:
            return jsonify({'error': 'Không có tệp'}), 400
       
        username = session['user'].get('username') or str(session['user'].get('id'))
        safe_name = ''.join(c for c in username if c.isalnum() or c in ('-', '_')).strip()
        user_id = session['user']['id']
        os.makedirs(config.FACES_DIR, exist_ok=True)
       
        file_extension = os.path.splitext(file.filename)[1] or '.jpg'
        # Đảm bảo tên file là TÊN USERNAME
        filename = os.path.join(config.FACES_DIR, f"{safe_name}{file_extension}")
       
        file.save(filename)
       
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute('SELECT * FROM face_data WHERE user_id=%s', (user_id,))
            if cur.fetchone():
                cur.execute('UPDATE face_data SET photo_path=%s WHERE user_id=%s', (filename, user_id))
            else:
                cur.execute('INSERT INTO face_data (user_id, photo_path) VALUES (%s, %s)', (user_id, filename))
            db.commit()
           
            cur.execute('UPDATE users SET face_registered=1 WHERE id=%s', (user_id,))
            db.commit()
           
            # ✨ TỐI ƯU HÓA: Tải lại khuôn mặt sau khi upload
            load_known_faces()
           
            return jsonify({'success': True, 'message': 'Đã tải lên khuôn mặt thành công'})
        except Exception as e:
            return jsonify({'error': f'Lỗi DB: {str(e)}'}), 500
        finally:
            cur.close()
            db.close()
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500


@app.route('/checkin', methods=['GET'])
def checkin_page():
    try:
        stations = get_all_stations()
    except Exception as e:
        stations = []
        print(f'Lỗi lấy danh sách ga: {e}')


    return render_template('checkin.html', stations=stations)


# ===================================================================
# ✨ TỐI ƯU HÓA TỐC ĐỘ (BƯỚC 3)
# Viết lại hoàn toàn hàm api_checkin để dùng RAM (siêu nhanh)
# ===================================================================
@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    try:
        data = request.json
        img_b64 = data.get('image_b64')
        # Key (khóa) là 'station' (TÊN GA), khớp với JS
        station_name = data.get('station')
       
        if not img_b64 or not station_name:
            return jsonify({'error': 'Thiếu dữ liệu image_b64 hoặc station'}), 400
       
        # 1. Giải mã ảnh (nhanh)
        img_bytes = base64.b64decode(img_b64.split(',')[-1])
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # img là BGR
       
        # 2. Tính encoding cho ảnh MỚI (bắt buộc)
        unknown_encodings = face_recognition.face_encodings(img)
       
        if not unknown_encodings:
            # Không tìm thấy mặt trong ảnh camera
            return jsonify({'success': False, 'reason': 'no_face_detected', 'message': 'Không phát hiện thấy khuôn mặt trong ảnh'})
       
        unknown_enc = unknown_encodings[0]
       
        # 3. Tách dữ liệu từ RAM (biến toàn cục)
        if not known_face_data:
             return jsonify({'success': False, 'reason': 'no_known_faces', 'message': 'Chưa có dữ liệu khuôn mặt nào trong hệ thống.'})
       
        known_usernames = [data[0] for data in known_face_data]
        known_encodings = [data[1] for data in known_face_data]


        # 4. So sánh (siêu nhanh vì so sánh trong RAM)
        distances = face_recognition.face_distance(known_encodings, unknown_enc)
        best_match_index = np.argmin(distances)
       
        matched_username = ""
       
        if distances[best_match_index] < config.FACE_RECOGNITION_TOLERANCE:
            matched_username = known_usernames[best_match_index]


        # 5. Xử lý kết quả (Logic cũ của bạn)
        if not matched_username:
            db = get_db()
            cur = db.cursor()
            try:
                # Ghi log 'no_match' vào 'checkins'
                cur.execute('''
                    INSERT INTO checkins (station, checkin_time, success, user_id, ticket_id)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (station_name, datetime.now(), 0, None, None))
                db.commit()
            finally:
                cur.close()
                db.close()
            return jsonify({'success': False, 'reason': 'no_match', 'message': 'Không tìm thấy khuôn mặt phù hợp'})
       
        # Đã khớp -> Tìm ID và kiểm tra vé
        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            # Dùng 'username' để tìm 'id'
            cur.execute("SELECT id FROM users WHERE username=%s", (matched_username,))
            user_row = cur.fetchone()
           
            if not user_row:
                return jsonify({'success': False, 'reason': 'user_not_found', 'message': f'Khuôn mặt khớp với {matched_username} nhưng không tìm thấy user trong CSDL'})
           
            matched_user_id = user_row['id']


            # Dùng ID (số) để kiểm tra vé
            cur.execute('''
                SELECT * FROM tickets
                WHERE user_id=%s AND status='NEW' AND ticket_type='monthly'
                ORDER BY purchase_time DESC
            ''', (matched_user_id,))
            tickets = cur.fetchall()
           
            allowed = False
            used_ticket_id = None
            reason = ''
            message = ''


            for t in tickets:
                valid_field = t.get('valid_from') or t.get('purchase_time')
                if valid_field:
                    valid_time = valid_field if isinstance(valid_field, datetime) else datetime.fromisoformat(str(valid_field))
                    now = datetime.now()
                    if (now - valid_time).days < 30:
                        allowed = True
                        used_ticket_id = t.get('id')
                        reason = 'monthly_ok'
                        message = 'Vé tháng hợp lệ - Vui lòng vào'
                        break
           
            if not allowed:
                if not tickets:
                    message = 'Không tìm thấy vé tháng'
                else:
                    message = 'Vé tháng không hợp lệ hoặc đã hết hạn'
           
            now = datetime.now()
           
            # Ghi log kết quả vào 'checkins'
            try:
                is_success = 1 if allowed else 0
                cur.execute('''
                    INSERT INTO checkins (ticket_id, user_id, station, checkin_time, success)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (used_ticket_id, matched_user_id, station_name, now, is_success))
                db.commit()
            except Exception as e:
                print(f"LỖI KHI GHI LOG CHECKIN: {e}")
                db.rollback()
           
            return jsonify({
                'success': allowed,
                'user_id': matched_user_id,
                'ticket_id': used_ticket_id,
                'reason': reason,
                'message': message
            })
        finally:
            cur.close()
            db.close()
   
    except Exception as e:
        print('Lỗi nghiêm trọng trong api_checkin:', e)
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Lỗi server nội bộ. Vui lòng kiểm tra log.'}), 500


@app.route('/history')
def history():
    if 'user' not in session:
        return redirect(url_for('login'))
   
    user_id = session['user']['id']
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('''
            SELECT t.id as ticket_id, t.status, t.purchase_time as purchase_time, t.valid_from as valid_from,
                   t.from_station_name, t.to_station_name
            FROM tickets t
            WHERE t.user_id=%s
            ORDER BY t.purchase_time DESC
        ''', (user_id,))
        tickets = cur.fetchall()
    except Exception as e:
        tickets = []
        print(f'Lỗi lấy lịch sử: {e}')
    finally:
        cur.close()
        db.close()
   
    for t in tickets:
        t['station_from'] = t.get('from_station_name')
        t['station_to'] = t.get('to_station_name')
        t['valid_at_datetime'] = t.get('valid_from')


    return render_template('history.html', tickets=tickets)


@app.route('/admin')
def admin():
    if 'user' not in session:
        return redirect(url_for('login'))
   
    if not is_admin():
        return render_template('admin_error.html', message='Bạn không có quyền truy cập'), 403
   
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT COUNT(*) as total_users FROM users WHERE role="user"')
        total_users = cur.fetchone()['total_users']
       
        cur.execute('SELECT COUNT(*) as total_tickets FROM tickets')
        total_tickets = cur.fetchone()['total_tickets']
       
        # SỬA LỖI 500: Đọc từ 'checkins'
        cur.execute('SELECT COUNT(*) as total_checkins FROM checkins WHERE success=1')
        total_checkins = cur.fetchone()['total_checkins']
       
        cur.execute('SELECT COUNT(*) as total_revenue FROM tickets WHERE status IN ("NEW", "USED") OR (status="NEW" AND ticket_type="monthly")')
        total_revenue_count = cur.fetchone()['total_revenue']
        total_revenue = total_revenue_count * 500000
       
        cur.execute('SELECT * FROM users WHERE role="user" ORDER BY id DESC')
        users = cur.fetchall()
       
        cur.execute('''
            SELECT t.*,
                   u.username,
                   t.from_station_name,
                   t.to_station_name
            FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.purchase_time DESC
        ''')
        tickets = cur.fetchall()
       
        # SỬA LỖI 500: Đọc từ 'checkins'
        cur.execute('''
            SELECT ci.id, ci.checkin_time as timestamp, ci.success, ci.station as station_name,
                   u.username
            FROM checkins ci
            LEFT JOIN users u ON ci.user_id = u.id
            ORDER BY ci.checkin_time DESC
            LIMIT 100
        ''')
        entry_logs = cur.fetchall()
    except Exception as e:
        print(f'Lỗi admin: {e}')
        traceback.print_exc()
        return render_template('admin_error.html', message=f'Lỗi tải dữ liệu: {str(e)}'), 500
    finally:
        cur.close()
        db.close()
   
    return render_template('admin.html',
                          total_users=total_users,
                          total_tickets=total_tickets,
                          total_checkins=total_checkins,
                          total_revenue=total_revenue,
                          users=users,
                          tickets=tickets,
                          entry_logs=entry_logs)


@app.route('/api/admin/user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user' not in session or not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
   
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute('DELETE FROM users WHERE id=%s AND role="user"', (user_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Xóa người dùng thành công'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        db.close()


@app.route('/api/admin/ticket/<int:ticket_id>', methods=['DELETE'])
def delete_ticket(ticket_id):
    if 'user' not in session or not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
   
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute('DELETE FROM tickets WHERE id=%s', (ticket_id,))
        db.commit()
        return jsonify({'success': True, 'message': 'Xóa vé thành công'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()
        db.close()


@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
def edit_user(user_id):
    if 'user' not in session or not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
   
    try:
        data = request.json
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
       
        if not all([username, email, phone]):
            return jsonify({'error': 'Vui lòng điền tất cả các trường'}), 400
       
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute(
                'UPDATE users SET username=%s, email=%s, phone=%s WHERE id=%s AND role="user"',
                (username, email, phone, user_id)
            )
            db.commit()
            return jsonify({'success': True, 'message': 'Cập nhật người dùng thành công'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cur.close()
            db.close()
    except Exception as e:
        return jsonify({'error': f'Lỗi: {str(e)}'}), 500


@app.route('/api/admin/stats', methods=['GET'])
def get_stats():
    if 'user' not in session or not is_admin():
        return jsonify({'error': 'Unauthorized'}), 403
   
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute('SELECT COUNT(*) as total_users FROM users WHERE role="user"')
        total_users = cur.fetchone()['total_users']
       
        cur.execute('SELECT COUNT(*) as total_tickets FROM tickets')
        total_tickets = cur.fetchone()['total_tickets']
       
        # SỬA LỖI 500: Đọc từ 'checkins'
        cur.execute('SELECT COUNT(*) as today_checkins FROM checkins WHERE DATE(checkin_time)=DATE(NOW())')
        today_checkins = cur.fetchone()['today_checkins']
       
        return jsonify({
            'total_users': total_users,
            'total_tickets': total_tickets,
            'today_checkins': today_checkins
        })
    finally:
        cur.close()
        db.close()


if __name__ == '__main__':
    os.makedirs(config.FACES_DIR, exist_ok=True)
    init_admin()
    DEFAULT_STATIONS = [
        'Ga Bến Thành',
        'Ga Nhà hát Thành phố',
        'Ga Ba Son',
        'Ga Công viên Văn Thánh',
        'Ga Tân Cảng',
        'Ga Thảo Điền',
        'Ga An Phú',
        'Ga Rạch Chiếc',
        'Ga Phước Long',
        'Ga Bình Thái',
        'Ga Thủ Đức',
        'Ga Khu Công nghệ cao',
        'Ga Đại học Quốc gia',
        'Ga Bến xe Suối Tiên'
    ]
    try:
        ensure_stations(DEFAULT_STATIONS)
    except Exception as e:
        print('Warning: ensure_stations failed:', e)
    try:
        ensure_face_data_table()
    except Exception as e:
        print('Warning: ensure_face_data_table failed:', e)
    try:
        ensure_tickets_schema()
    except Exception as e:
        print('Warning: ensure_tickets_schema failed:', e)
   
    # ===================================================================
    # ✨ TỐI ƯU HÓA TỐC ĐỘ (BƯỚC 4)
    # Gọi hàm tải khuôn mặt 1 LẦN DUY NHẤT khi khởi động server
    # ===================================================================
    try:
        load_known_faces()
    except Exception as e:
        print('Warning: load_known_faces failed:', e)


    app.run(host='0.0.0.0', port=5000, debug=True)




# ===================================================================