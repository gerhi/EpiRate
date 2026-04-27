"""Authentifizierung und Autorisierung – Decorators und Passwort-Utilities.

Zwei Rollen: ADMIN (voller Zugriff) und MANAGER (eingeschränkt).
Öffentliche Nutzer authentifizieren sich per Einmal-Token statt Passwort.
"""

from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db_connection


def admin_required(f):
    """Nur Rolle ADMIN – für Nutzerverwaltung und destruktive Aktionen."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session or not session["admin_logged_in"]:
            return redirect(url_for("admin.login"))
        if session.get("admin_role") != "ADMIN":
            flash("Sie haben keine Berechtigung für diese Seite.", "danger")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    """ADMIN oder MANAGER – für allgemeine Backend-Funktionen."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin_logged_in" not in session or not session["admin_logged_in"]:
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated_function


def token_required(f):
    """Prüft, ob ein gültiger Einmal-Token in der Session liegt (öffentliche Umfrage)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "token_id" not in session:
            flash("Bitte geben Sie einen gültigen Token ein.", "warning")
            return redirect(url_for("public.login"))

        token_id = session["token_id"]
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, used FROM tokens WHERE id = %s", (token_id,))
                token_data = cur.fetchone()
                if not token_data or token_data["used"]:
                    session.clear()
                    flash("Ihr Token ist ungültig oder wurde bereits verwendet. Bitte melden Sie sich erneut an.", "danger")
                    return redirect(url_for("public.login"))
        finally:
            conn.close()
        return f(*args, **kwargs)
    return decorated_function


def hash_password(password):
    """Erzeugt einen sicheren Hash (pbkdf2) für neue Passwörter."""
    return generate_password_hash(password)


def verify_password(stored_hash, password, username=None):
    """Verifiziert ein Passwort – unterstützt auch alte SHA-256-Hashes (Abwärtskompatibilität).
    Bei erfolgreicher SHA-256-Prüfung wird der Hash automatisch auf pbkdf2 migriert.
    """
    # Alt-Hashes erkennen: 64 Hex-Zeichen = unsalted SHA-256
    if len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash):
        import hashlib
        if hashlib.sha256(password.encode()).hexdigest() == stored_hash:
            if username:
                _upgrade_password_hash(username, password)
            return True
        return False
    return check_password_hash(stored_hash, password)


def _upgrade_password_hash(username, password):
    """Migriert einen unsicheren SHA-256-Hash auf pbkdf2 (einmaliger Auto-Upgrade)."""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE admins SET password = %s WHERE username = %s",
                            (generate_password_hash(password), username))
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
