"""Datenbank-Verbindung – Caller muss conn.close() im finally-Block aufrufen."""

import pymysql
from flask import current_app


def get_db_connection():
    """Neue DB-Verbindung mit DictCursor (Zeilen als dict statt tuple)."""
    return pymysql.connect(
        host=current_app.config["MYSQL_HOST"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        db=current_app.config["MYSQL_DB"],
        cursorclass=pymysql.cursors.DictCursor,
    )
