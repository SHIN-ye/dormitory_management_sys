
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    MYSQL_USER = os.environ.get("MYSQL_USER") or "root"
    MYSQL_PWD = os.environ.get("MYSQL_PWD") or "123456"
    MYSQL_HOST = os.environ.get("MYSQL_HOST") or "localhost"
    MYSQL_PORT = os.environ.get("MYSQL_PORT") or "3306"
    MYSQL_DB = os.environ.get("MYSQL_DB") or "dormitory_management"

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PWD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
        "?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "mp4", "webm", "avi", "mov"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
