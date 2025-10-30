# from flask import Flask, render_template, request, redirect, url_for, session, jsonify
# from flask_cors import CORS
# import mysql.connector
# from datetime import datetime
# import os, uuid, hashlib, base64, cv2

# import config

# try:
#     import face_recognition
#     FACE_LIB = 'face_recognition'
# except Exception as e:
#     print('face_recognition not available, fallback to opencv LBPH:', e)
#     FACE_LIB = 'opencv_fallback'

# app = Flask(__name__)
# CORS(app)
# app.secret_key = 'replace_with_secret'

# def get_db():
#     return mysql.connector.connect(
#         host=config.DB_HOST,
#         port=config.DB_PORT,
#         user=config.DB_USER,
#         password=config.DB_PASSWORD,
#         database=config.DB_NAME,
#         autocommit=True
#     )

# def hash_pw(pw):
#     return hashlib.sha256(pw.encode()).hexdigest()

# @app.route('/')
# def home():
#     return render_template('index.html')

# @app.route('/register', methods=['GET','POST'])
# def register():
#     if request.method == 'POST':
#         username = request.form['username']
#         phone = request.form['phone']
#         email = request.form['email']
#         password = hash_pw(request.form['password'])
#         db = get_db(); cur = db.cursor()
#         try:
#             cur.execute('INSERT INTO users (username,phone,email,password) VALUES (%s,%s,%s,%s)',
#                         (username,phone,email,password))
#             db.commit()
#             return redirect(url_for('login'))
#         except Exception as e:
#             return f"Registration error: {e}"
#     return render_template('register.html')

# @app.route('/login', methods=['GET','POST'])
# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = hash_pw(request.form['password'])
#         db = get_db(); cur = db.cursor(dictionary=True)
#         cur.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username,password))
#         user = cur.fetchone()
#         if user:
#             session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role']}
#             return redirect(url_for('home'))
#         else:
#             return 'Invalid credentials'
#     return render_template('login.html')

# @app.route('/logout')
# def logout():
#     session.pop('user', None)
#     return redirect(url_for('home'))

# @app.route('/buy_ticket', methods=['GET','POST'])
# def buy_ticket():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     if request.method=='POST':
#         user_id = session['user']['id']
#         ttype = request.form['type']
#         now = datetime.now()
#         trip_code = str(uuid.uuid4())
#         db = get_db(); cur = db.cursor()
#         if ttype=='monthly':
#             vf = request.form.get('valid_from')
#             vt = request.form.get('valid_to')
#             cur.execute('INSERT INTO tickets (user_id,ticket_type,purchase_time,valid_from,valid_to,trip_code) VALUES (%s,%s,%s,%s,%s,%s)',
#                         (user_id,ttype,now,vf,vt,trip_code))
#         else:
#             from_s = request.form.get('from_station')
#             to_s = request.form.get('to_station')
#             cur.execute('INSERT INTO tickets (user_id,ticket_type,purchase_time,single_from_station,single_to_station,trip_code) VALUES (%s,%s,%s,%s,%s,%s)',
#                         (user_id,ttype,now,from_s,to_s,trip_code))
#         db.commit()
#         return redirect(url_for('history'))
#     return render_template('buy_ticket.html')

# @app.route('/history')
# def history():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     user_id = session['user']['id']
#     db = get_db(); cur = db.cursor(dictionary=True)
#     cur.execute('SELECT * FROM tickets WHERE user_id=%s ORDER BY purchase_time DESC', (user_id,))
#     tickets = cur.fetchall()
#     return render_template('history.html', tickets=tickets)

# @app.route('/admin')
# def admin():
#     if 'user' not in session or session['user']['role']!='admin':
#         return 'Access denied'
#     db = get_db(); cur = db.cursor(dictionary=True)
#     cur.execute('SELECT * FROM users')
#     users = cur.fetchall()
#     cur.execute('SELECT t.*, u.username FROM tickets t LEFT JOIN users u ON t.user_id=u.id')
#     tickets = cur.fetchall()
#     return render_template('admin.html', users=users, tickets=tickets)

# @app.route('/upload_face', methods=['GET'])
# def upload_face_page():
#     if 'user' not in session:
#         return redirect(url_for('login'))
#     return render_template('upload_face.html')

# @app.route('/api/upload_face', methods=['POST'])
# def upload_face():
#     if 'user' not in session:
#         return jsonify({'error':'not logged in'}),403
#     file = request.files.get('face')
#     if not file:
#         return jsonify({'error':'no file'}),400
#     user_id = session['user']['id']
#     os.makedirs(config.FACES_DIR, exist_ok=True)
#     filename = os.path.join(config.FACES_DIR, f"{user_id}.jpg")
#     file.save(filename)
#     db = get_db(); cur = db.cursor()
#     cur.execute('UPDATE users SET face_registered=1 WHERE id=%s', (user_id,))
#     db.commit()
#     return redirect(url_for('home'))

# def opencv_match(img, known_img):
#     # simplistic LBPH compare: train recognizer on known image(s) and predict on img
#     gray_known = cv2.cvtColor(known_img, cv2.COLOR_BGR2GRAY)
#     gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
#     recognizer = cv2.face.LBPHFaceRecognizer_create()
#     # labels: [1]
#     recognizer.train([gray_known], [1])
#     label, confidence = recognizer.predict(gray_img)
#     return label, confidence

# @app.route('/api/checkin', methods=['POST'])
# def api_checkin():
#     data = request.json
#     img_b64 = data.get('image_b64')
#     station = data.get('station')
#     if not img_b64:
#         return jsonify({'error':'no image'}),400
#     img_bytes = base64.b64decode(img_b64.split(',')[-1])
#     import numpy as np
#     nparr = np.frombuffer(img_bytes, np.uint8)
#     img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

#     matches = []
#     if not os.path.exists(config.FACES_DIR):
#         os.makedirs(config.FACES_DIR, exist_ok=True)
#     for fname in os.listdir(config.FACES_DIR):
#         if not fname.lower().endswith(('.jpg','.png','jpeg')): continue
#         user_id = int(os.path.splitext(fname)[0])
#         known = cv2.imread(os.path.join(config.FACES_DIR, fname))
#         try:
#             if FACE_LIB=='face_recognition':
#                 known_enc = face_recognition.face_encodings(known)
#                 if not known_enc: continue
#                 known_enc = known_enc[0]
#                 unknown_enc = face_recognition.face_encodings(img)
#                 if not unknown_enc: continue
#                 unknown_enc = unknown_enc[0]
#                 d = face_recognition.face_distance([known_enc], unknown_enc)[0]
#                 if d < 0.5:
#                     matches.append((user_id, d))
#             else:
#                 label, confidence = opencv_match(img, known)
#                 # lower confidence is better in LBPH, threshold example < 70
#                 if confidence < 70:
#                     matches.append((user_id, confidence))
#         except Exception as e:
#             print('compare error', e)
#     if not matches:
#         return jsonify({'success':False, 'reason':'no_match'})
#     matches.sort(key=lambda x: x[1])
#     matched_user = matches[0][0]

#     db = get_db(); cur = db.cursor(dictionary=True)
#     cur.execute("SELECT * FROM tickets WHERE user_id=%s ORDER BY purchase_time DESC", (matched_user,))
#     tickets = cur.fetchall()
#     allowed = False
#     used_ticket_id = None
#     reason = ''
#     for t in tickets:
#         if t['ticket_type']=='monthly':
#             today = datetime.now().date()
#             if t['valid_from'] and t['valid_to'] and (t['valid_from'] <= today <= t['valid_to']):
#                 allowed = True
#                 used_ticket_id = t['id']
#                 reason = 'monthly_ok'
#                 break
#         else:
#             if t['used'] == 1:
#                 continue
#             if t['single_from_station'] == station:
#                 allowed = True
#                 used_ticket_id = t['id']
#                 reason = 'single_entry_ok'
#                 break
#     now = datetime.now()
#     cur.execute('INSERT INTO checkins (ticket_id,user_id,station,checkin_time,success) VALUES (%s,%s,%s,%s,%s)',
#                 (used_ticket_id, matched_user, station, now, 1 if allowed else 0))
#     db.commit()
#     return jsonify({'success': allowed, 'user_id': matched_user, 'ticket_id': used_ticket_id, 'reason': reason})

# if __name__=='__main__':
#     os.makedirs(config.FACES_DIR, exist_ok=True)
#     app.run(host='0.0.0.0', port=5000, debug=True)
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import os, uuid, hashlib, base64, cv2

import config

try:
    import face_recognition
    FACE_LIB = 'face_recognition'
except Exception as e:
    print('face_recognition not available, fallback to opencv LBPH:', e)
    FACE_LIB = 'opencv_fallback'

app = Flask(__name__)
CORS(app)
app.secret_key = 'replace_with_secret'

# ==========================
# DATABASE CONNECTION
# ==========================
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

# ==========================
# ROUTES
# ==========================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        phone = request.form['phone']
        email = request.form['email']
        password = hash_pw(request.form['password'])
        db = get_db(); cur = db.cursor()
        try:
            cur.execute('INSERT INTO users (username,phone,email,password) VALUES (%s,%s,%s,%s)',
                        (username,phone,email,password))
            db.commit()
            return redirect(url_for('login'))
        except Exception as e:
            return f"Registration error: {e}"
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = hash_pw(request.form['password'])
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute('SELECT * FROM users WHERE username=%s AND password=%s', (username,password))
        user = cur.fetchone()
        if user:
            session['user'] = {'id': user['id'], 'username': user['username'], 'role': user['role']}
            return redirect(url_for('home'))
        else:
            return 'Invalid credentials'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('home'))

@app.route('/buy_ticket', methods=['GET','POST'])
def buy_ticket():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method=='POST':
        user_id = session['user']['id']
        ttype = request.form['type']
        now = datetime.now()
        trip_code = str(uuid.uuid4())
        db = get_db(); cur = db.cursor()
        if ttype=='monthly':
            vf = request.form.get('valid_from')
            vt = request.form.get('valid_to')
            cur.execute('INSERT INTO tickets (user_id,ticket_type,purchase_time,valid_from,valid_to,trip_code) VALUES (%s,%s,%s,%s,%s,%s)',
                        (user_id,ttype,now,vf,vt,trip_code))
        else:
            from_s = request.form.get('from_station')
            to_s = request.form.get('to_station')
            cur.execute('INSERT INTO tickets (user_id,ticket_type,purchase_time,single_from_station,single_to_station,trip_code) VALUES (%s,%s,%s,%s,%s,%s)',
                        (user_id,ttype,now,from_s,to_s,trip_code))
        db.commit()
        return redirect(url_for('history'))
    return render_template('buy_ticket.html')

@app.route('/history')
def history():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_id = session['user']['id']
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM tickets WHERE user_id=%s ORDER BY purchase_time DESC', (user_id,))
    tickets = cur.fetchall()
    return render_template('history.html', tickets=tickets)

@app.route('/admin')
def admin():
    if 'user' not in session or session['user']['role']!='admin':
        return 'Access denied'
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute('SELECT * FROM users')
    users = cur.fetchall()
    cur.execute('SELECT t.*, u.username FROM tickets t LEFT JOIN users u ON t.user_id=u.id')
    tickets = cur.fetchall()
    return render_template('admin.html', users=users, tickets=tickets)

@app.route('/upload_face', methods=['GET'])
def upload_face_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('upload_face.html')

@app.route('/api/upload_face', methods=['POST'])
def upload_face():
    if 'user' not in session:
        return jsonify({'error':'not logged in'}),403
    file = request.files.get('face')
    if not file:
        return jsonify({'error':'no file'}),400
    user_id = session['user']['id']
    os.makedirs(config.FACES_DIR, exist_ok=True)
    filename = os.path.join(config.FACES_DIR, f"{user_id}.jpg")
    file.save(filename)
    db = get_db(); cur = db.cursor()
    cur.execute('UPDATE users SET face_registered=1 WHERE id=%s', (user_id,))
    db.commit()
    return redirect(url_for('home'))

# ==========================
# FACE RECOGNITION
# ==========================
def opencv_match(img, known_img):
    gray_known = cv2.cvtColor(known_img, cv2.COLOR_BGR2GRAY)
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train([gray_known], [1])
    label, confidence = recognizer.predict(gray_img)
    return label, confidence

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.json
    img_b64 = data.get('image_b64')
    station = data.get('station')
    if not img_b64:
        return jsonify({'error':'no image'}),400
    img_bytes = base64.b64decode(img_b64.split(',')[-1])
    import numpy as np
    nparr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    matches = []
    if not os.path.exists(config.FACES_DIR):
        os.makedirs(config.FACES_DIR, exist_ok=True)
    for fname in os.listdir(config.FACES_DIR):
        if not fname.lower().endswith(('.jpg','.png','.jpeg')): continue
        user_id = int(os.path.splitext(fname)[0])
        known = cv2.imread(os.path.join(config.FACES_DIR, fname))
        try:
            if FACE_LIB=='face_recognition':
                known_enc = face_recognition.face_encodings(known)
                if not known_enc: continue
                known_enc = known_enc[0]
                unknown_enc = face_recognition.face_encodings(img)
                if not unknown_enc: continue
                unknown_enc = unknown_enc[0]
                d = face_recognition.face_distance([known_enc], unknown_enc)[0]
                if d < 0.5:
                    matches.append((user_id, d))
            else:
                label, confidence = opencv_match(img, known)
                if confidence < 70:
                    matches.append((user_id, confidence))
        except Exception as e:
            print('compare error', e)
    if not matches:
        return jsonify({'success':False, 'reason':'no_match'})
    matches.sort(key=lambda x: x[1])
    matched_user = matches[0][0]

    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM tickets WHERE user_id=%s ORDER BY purchase_time DESC", (matched_user,))
    tickets = cur.fetchall()
    allowed = False
    used_ticket_id = None
    reason = ''
    for t in tickets:
        if t['ticket_type']=='monthly':
            today = datetime.now().date()
            if t['valid_from'] and t['valid_to'] and (t['valid_from'] <= today <= t['valid_to']):
                allowed = True
                used_ticket_id = t['id']
                reason = 'monthly_ok'
                break
        else:
            if t.get('used') == 1:
                continue
            if t['single_from_station'] == station:
                allowed = True
                used_ticket_id = t['id']
                reason = 'single_entry_ok'
                break
    now = datetime.now()
    cur.execute('INSERT INTO checkins (ticket_id,user_id,station,checkin_time,success) VALUES (%s,%s,%s,%s,%s)',
                (used_ticket_id, matched_user, station, now, 1 if allowed else 0))
    db.commit()
    return jsonify({'success': allowed, 'user_id': matched_user, 'ticket_id': used_ticket_id, 'reason': reason})

# ✅ GIAO DIỆN CHECKIN
@app.route('/checkin')
def checkin_page():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('checkin.html')

# ==========================
# MAIN
# ==========================
if __name__ == '__main__':
    os.makedirs(config.FACES_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
