# config.py

DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASSWORD = 'h9minhhuy'  # 👉 sửa thành mật khẩu MySQL thật của bạn (nếu có)
DB_NAME = 'metro_facecheck'

# Thư mục lưu khuôn mặt
FACES_DIR = 'uploads/faces'

# Face Recognition Settings
FACE_RECOGNITION_TOLERANCE = 0.5  # Độ chính xác nhận diện khuôn mặt (0-1, thấp hơn = chính xác hơn