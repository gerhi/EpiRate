"""Zentrale App-Konfiguration – lädt sensible Werte aus .env (siehe .env.example)."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is not set. See .env.example")

    # Datenbank
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DB = os.environ.get("MYSQL_DB", "")

    FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")

    # Session-Cookie-Sicherheit
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 14400  # 4 Stunden

    # Dateisystem-Pfade relativ zum Projektroot
    UPLOAD_FOLDER = "static/qrcodes"
    UPLOAD_FOLDER_EXCEL = "uploads"
    ALLOWED_EXTENSIONS = {"xlsx", "xls"}
