import os
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def build_mysql_uri():
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "upms_teamup")
    user = os.getenv("DB_USER", "root")
    pwd = os.getenv("DB_PASSWORD", "")
    # mysql+pymysql://user:pass@host:port/db?charset=utf8mb4
    # IMPORTANT: if password is blank, do NOT include ':' (it breaks some environments)
    if pwd:
        safe_pwd = quote_plus(pwd)
        return f"mysql+pymysql://{user}:{safe_pwd}@{host}:{port}/{name}?charset=utf8mb4"
    return f"mysql+pymysql://{user}@{host}:{port}/{name}?charset=utf8mb4"

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", build_mysql_uri())
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(25 * 1024 * 1024)))  # 25MB default
    ALLOWED_IMAGE_EXTENSIONS = set(os.getenv("ALLOWED_IMAGE_EXTENSIONS", "png,jpg,jpeg,webp").split(","))
    ALLOWED_PDF_EXTENSIONS = {"pdf"}




import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
    MAX_IMAGE_SIZE_MB = 5

    # Database
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    # Uploads
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")

    # SMTP (Email Verification)
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_FROM = os.getenv("SMTP_FROM")

    # OTP / Verification
    OTP_EXP_MINUTES = int(os.getenv("OTP_EXP_MINUTES", 10))
    OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", 5))
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", 60))
