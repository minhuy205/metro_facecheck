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
    known_face_data = []
   
    # Đã tắt log khởi động (theo yêu cầu trước)
    # print("Đang tải dữ liệu khuôn mặt đã biết vào bộ nhớ...")
   
    if not os.path.exists(config.FACES_DIR):
        # print(f"Thư mục '{config.FACES_DIR}' không tồn tại. Bỏ qua.")
        return


    for fname in os.listdir(config.FACES_DIR):
        if not fname.lower().endswith(('.jpg', '.png', '.jpeg')):
            continue
       
        try:
            username = os.path.splitext(fname)[0]
            image_path = os.path.join(config.FACES_DIR, fname)
            known_image = cv2.imread(image_path)
           
            if known_image is None:
                print(f"Không thể đọc file: {fname}")
                continue
           
            rgb_image = cv2.cvtColor(known_image, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_image)
           
            if encodings:
                known_face_data.append((username, encodings[0]))
                # print(f"-> Đã tải xong khuôn mặt cho: {username}")
            else:
                # print(f"Không tìm thấy khuôn mặt trong: {fname}")
                pass
        except Exception as e:
            print(f"Lỗi khi tải {fname}: {e}")
   
    # print(f"Đã tải thành công {len(known_face_data)} khuôn mặt vào bộ nhớ.")
# ===================================================================




def detect_station_columns():
    """Phát hiện tên cột của bảng `stations`."""
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='stations'", (config.DB_NAME,))
        cols = [r[0] for r in cur.fetchall()]
        cur.close()
        db.close()
        if 'station_name' in cols:
            id_col = 'station_id' if 'station_id' in cols else 'id'
            return (id_col, 'station_name')
        if 'id' in cols and 'name' in cols:
            return ('id', 'name')
        if len(cols) >= 2:
            return (cols[0], cols[1])
    except Exception as e:
        print('detect_station_columns error:', e)
    return ('station_id', 'station_name')




def get_table_columns(table_name):
    """Lấy danh sách tên cột của một bảng."""
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
    """Lấy danh sách các ga."""
    id_col, name_col = detect_station_columns()
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        # Dùng TÊN GA làm ID (value)
        q = f"SELECT {name_col} AS station_id, {name_col} AS station_name FROM stations ORDER BY {name_col}"
        cur.execute(q)
        stations = cur.fetchall()
        return stations
    except Exception as e:
        print('get_all_stations error:', e)
        return []
    finally:
        cur.close()
        db.close()




def ensure_stations(station_names):
    """Đảm bảo các ga mặc định tồn tại."""
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
    """Đảm bảo bảng face_data tồn tại."""
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
        try: cur.close(); db.close()
        except Exception: pass




def ensure_tickets_schema():
    """Đảm bảo bảng tickets có các cột cần thiết."""
    try:
        cols = get_table_columns('tickets')
        db = get_db()
        cur = db.cursor()
        alters = []
        want = {
            'user_id': 'INT', 'ticket_type': 'VARCHAR(50)', 'purchase_time': 'DATETIME',
            'valid_from': 'DATETIME', 'valid_to': 'DATETIME', 'from_station_id': 'INT',
            'to_station_id': 'INT', 'from_station_name': 'VARCHAR(255)',
            'to_station_name': 'VARCHAR(255)', 'single_from_station': 'VARCHAR(255)',
            'single_to_station': 'VARCHAR(255)', 'status': 'VARCHAR(20)',
            'purchase_price': 'INT', 'used': 'TINYINT(1)', 'trip_code': 'VARCHAR(100)'
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
    """Kiểm tra user có vé tháng còn hạn không."""
    try:
        db = get_db()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM tickets WHERE user_id=%s AND ticket_type='monthly' AND status='NEW'", (user_id,))
        rows = cur.fetchall()
        cur.close()
        db.close()
        for ex in rows:
            valid_from = ex.get('valid_from') or ex.get('purchase_time')
            if valid_from:
                try:
                    vf = valid_from if isinstance(valid_from, datetime) else datetime.fromisoformat(str(valid_from))
                    if (datetime.now() - vf).days < 30:
                        return True
                except Exception:
                    continue
        return False
    except Exception as e:
        print('user_has_active_monthly error:', e)
        return False




def user_has_face(user_id):
    """Kiểm tra user đã đăng ký khuôn mặt chưa."""
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
    """Tạo tài khoản admin nếu chưa có."""
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
            # print('Tài khoản admin đã được tạo (tên: admin, mật khẩu: admin123)') # Đã tắt
        cur.close()
        db.close()
    except Exception as e:
        print(f'Lỗi khởi tạo admin: {e}')


def is_admin():
    """Kiểm tra session có phải là admin không."""
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
        role = 'user'
       
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
                session['user'] = {
                    'id': user.get('id'),
                    'username': user.get('username'),
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
    try:
        stations = get_all_stations()
        return jsonify({'stations': stations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
       
        ticket_type = 'monthly'
        trip_code = str(uuid.uuid4())


        if has_active:
            return render_template('buy_ticket.html', error='Bạn đã có vé tháng đang hoạt động.', stations=stations, has_active=has_active, has_face=has_face)
       
        station_from_name = request.form.get('station_from_id')
        station_to_name = request.form.get('station_to_id')
       
        if not station_from_name or not station_to_name:
            return render_template('buy_ticket.html', error='Vui lòng chọn ga đi và ga đến', stations=stations, has_active=has_active, has_face=has_face)


        db = get_db()
        cur = db.cursor()
        try:
            cols = [
                'user_id', 'ticket_type', 'purchase_time', 'valid_from',
                'from_station_name', 'to_station_name', 'status',
                'purchase_price', 'used', 'trip_code'
            ]
            vals = [
                user_id, ticket_type, now, now,
                station_from_name, station_to_name, 'NEW',
                500000, 0, trip_code
            ]


            placeholders = ','.join(['%s'] * len(vals))
            q = f"INSERT INTO tickets ({', '.join(cols)}) VALUES ({placeholders})"
            cur.execute(q, tuple(vals))
            db.commit()
           
            if has_face:
                return redirect(url_for('history'))
            else:
                return redirect(url_for('upload_face_page'))
       
        except Exception as e:
            traceback.print_exc()
            return render_template('buy_ticket.html', error=f'Lỗi mua vé: {str(e)}', stations=stations, has_active=has_active, has_face=has_face)
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
       
        username = session['user'].get('username')
        safe_name = ''.join(c for c in username if c.isalnum() or c in ('-', '_')).strip()
        user_id = session['user']['id']
        os.makedirs(config.FACES_DIR, exist_ok=True)
       
        file_extension = os.path.splitext(file.filename)[1] or '.jpg'
       
        for f in os.listdir(config.FACES_DIR):
            if f.startswith(safe_name + '.'):
                try:
                    os.remove(os.path.join(config.FACES_DIR, f))
                except Exception as e:
                    print(f"Không thể xóa file cũ: {e}")


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
           
            load_known_faces() # Tải lại khuôn mặt sau khi upload
           
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




@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    try:
        data = request.json
        img_b64 = data.get('image_b64')
        station_name = data.get('station') # Key là 'station' (TÊN GA)
       
        if not img_b64 or not station_name:
            return jsonify({'error': 'Thiếu dữ liệu image_b64 hoặc station'}), 400
       
        # 1. Giải mã ảnh
        img_bytes = base64.b64decode(img_b64.split(',')[-1])
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
       
        # 2. Tính encoding ảnh mới
        unknown_encodings = face_recognition.face_encodings(rgb_image)
       
        if not unknown_encodings:
            return jsonify({'success': False, 'reason': 'no_face_detected', 'message': 'Không phát hiện thấy khuôn mặt trong ảnh'})
       
        unknown_enc = unknown_encodings[0]
       
        # 3. Lấy dữ liệu từ RAM
        if not known_face_data:
             return jsonify({'success': False, 'reason': 'no_known_faces', 'message': 'Chưa có dữ liệu khuôn mặt nào trong hệ thống.'})
       
        known_usernames = [data[0] for data in known_face_data]
        known_encodings = [data[1] for data in known_face_data]


        # 4. So sánh
        distances = face_recognition.face_distance(known_encodings, unknown_enc)
        best_match_index = np.argmin(distances)
        matched_username = ""
       
        if distances[best_match_index] < 0.6:
            matched_username = known_usernames[best_match_index]


        # 5. Xử lý kết quả
        if not matched_username:
            db = get_db(); cur = db.cursor()
            try:
                cur.execute('''
                    INSERT INTO checkins (station, checkin_time, success, user_id, ticket_id)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (station_name, datetime.now(), 0, None, None))
                db.commit()
            finally:
                cur.close(); db.close()
            return jsonify({'success': False, 'reason': 'no_match', 'message': 'Không tìm thấy khuôn mặt phù hợp'})
       
        # Đã khớp -> Tìm ID và kiểm tra vé
        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute("SELECT id FROM users WHERE username=%s", (matched_username,))
            user_row = cur.fetchone()
           
            if not user_row:
                return jsonify({'success': False, 'reason': 'user_not_found', 'message': f'Khuôn mặt khớp với {matched_username} nhưng không tìm thấy user trong CSDL'})
           
            matched_user_id = user_row['id']
           
            # ✨✨✨ LOGIC MỚI: CHỐNG GIAN LẬN (5 PHÚT) - ĐÃ SỬA THEO YÊU CẦU ✨✨✨
            now = datetime.now() # Lấy thời gian hiện tại
           
            # 1. Lấy check-in THÀNH CÔNG (success=1) GẦN NHẤT
            cur.execute("SELECT station, checkin_time FROM checkins WHERE user_id = %s AND success = 1 ORDER BY checkin_time DESC LIMIT 1", (matched_user_id,))
            last_log = cur.fetchone()
           
            if last_log:
                last_time = last_log['checkin_time']
                last_station = last_log['station']
                time_diff_seconds = (now - last_time).total_seconds()
               
                # 2. Nếu (thời gian < 5 phút) -> LUÔN LUÔN LÀ LỖI
                if time_diff_seconds < 300: # 5 phút = 300 giây
                   
                    # Ghi log thất bại (vì user đang cố check-in)
                    cur.execute('''
                        INSERT INTO checkins (ticket_id, user_id, station, checkin_time, success)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (None, matched_user_id, station_name, now, 0)) # success=0
                    db.commit()
                   
                    # Trả về lỗi tiếng Việt
                    return jsonify({
                        'success': False,
                        'user_id': matched_user_id,
                        'reason': 'rapid_checkin_denied',
                        'message': f'LỖI: Bạn vừa check-in tại "{last_station}" {int(time_diff_seconds // 60)} phút {int(time_diff_seconds % 60)} giây trước.'
                    })
           
            # ✨✨✨ HẾT LOGIC CHỐNG GIAN LẬN ✨✨✨


            # Nếu > 5 phút (hoặc là lần check-in đầu tiên), tiếp tục kiểm tra vé
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
                    if (datetime.now() - valid_time).days < 30:
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
           
            # 'now' đã được định nghĩa ở trên
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
            SELECT
                t.id,
                t.status,
                t.purchase_time,
                t.valid_from,
                t.from_station_name,
                t.to_station_name,
                t.ticket_type,
                t.trip_code,
                t.used
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
       
        cur.execute('SELECT COUNT(*) as total_checkins FROM checkins WHERE success=1')
        total_checkins = cur.fetchone()['total_checkins']
       
        cur.execute('SELECT COUNT(*) as total_revenue FROM tickets WHERE (status="NEW" AND ticket_type="monthly") OR used=1')
        total_revenue_count = cur.fetchone()['total_revenue']
        total_revenue = total_revenue_count * 500000
       
        cur.execute('SELECT id, username, email, phone, face_registered FROM users WHERE role="user" ORDER BY id DESC')
        users = cur.fetchall()
       
        cur.execute('''
            SELECT t.*,
                   u.username
            FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            ORDER BY t.purchase_time DESC
        ''')
        tickets = cur.fetchall()
       
        cur.execute('''
            SELECT ci.id as log_id, ci.checkin_time as timestamp, ci.success, ci.station as station_name,
                   u.username
            FROM checkins ci
            LEFT JOIN users u ON ci.user_id = u.id
            ORDER BY ci.checkin_time DESC
            LIMIT 100
        ''')
        entry_logs = cur.fetchall()
       
        # ✨ YÊU CẦU MỚI: Thêm truy vấn thống kê ga ✨
        cur.execute('''
            SELECT
                station as station_name,
                COUNT(*) as total_checkins,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_checkins
            FROM checkins
            WHERE station IS NOT NULL AND station != ''
            GROUP BY station
            ORDER BY total_checkins DESC
        ''')
        station_stats = cur.fetchall()
        # ✨ --- Hết code mới --- ✨
       
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
                          entry_logs=entry_logs,
                          station_stats=station_stats # ✨ Thêm biến mới cho template
                          )


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
       
        cur.execute('SELECT COUNT(*) as today_checkins FROM checkins WHERE DATE(checkin_time)=DATE(NOW()) AND success=1')
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
   
    # Tải khuôn mặt vào RAM khi khởi động
    try:
        load_known_faces()
    except Exception as e:
        print('Warning: load_known_faces failed:', e)


    app.run(host='0.0.0.0', port=5000, debug=True)


# ===================================================================