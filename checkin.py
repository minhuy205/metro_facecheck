# checkin.py
import cv2
import face_recognition
import mysql.connector
import os
import numpy as np
from datetime import datetime
from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, FACES_DIR

# --- Kết nối database ---
def get_db():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

# --- Nạp dữ liệu khuôn mặt ---
def load_known_faces():
    known_encodings = []
    known_names = []

    for filename in os.listdir(FACES_DIR):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            path = os.path.join(FACES_DIR, filename)
            image = face_recognition.load_image_file(path)
            encoding = face_recognition.face_encodings(image)[0]
            name = os.path.splitext(filename)[0]
            known_encodings.append(encoding)
            known_names.append(name)
    return known_encodings, known_names


def log_checkin(user_id, status):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO checkins (user_id, status, time) VALUES (%s, %s, %s)",
        (user_id, status, datetime.now())
    )
    db.commit()
    db.close()


# --- Main ---
print("🎥 Mở camera, đang tải dữ liệu khuôn mặt...")
known_faces, known_names = load_known_faces()
video = cv2.VideoCapture(0)

while True:
    ret, frame = video.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    for face_encoding in face_encodings:
        matches = face_recognition.compare_faces(known_faces, face_encoding, tolerance=0.5)
        face_distances = face_recognition.face_distance(known_faces, face_encoding)
        best_match_index = np.argmin(face_distances)

        if matches[best_match_index]:
            name = known_names[best_match_index]
            print(f"✅ {name} hợp lệ – mở cổng!")

            # Lưu log check-in
            db = get_db()
            cur = db.cursor()
            cur.execute("SELECT id FROM users WHERE username=%s", (name,))
            user = cur.fetchone()
            if user:
                log_checkin(user[0], "success")

        else:
            print("❌ Không nhận diện được khuôn mặt hợp lệ")

    cv2.imshow("Metro Check-in", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video.release()
cv2.destroyAllWindows()
