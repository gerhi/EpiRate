"""Blueprint-Registrierung – wird von create_app() aufgerufen."""

from app.routes.public import public_bp
from app.routes.admin import admin_bp
from app.routes.api import api_bp


def register_blueprints(app):
    app.register_blueprint(public_bp)             # / – öffentliche Umfrage-Seiten
    app.register_blueprint(admin_bp, url_prefix="/admin")  # /admin – Backend
    app.register_blueprint(api_bp, url_prefix="/api")      # /api – REST-Schnittstelle
