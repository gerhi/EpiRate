"""Gemeinsame Hilfsfunktionen, die in mehreren Blueprints verwendet werden."""

from flask import current_app


def allowed_file(filename):
    """Prüft Dateiendung gegen ALLOWED_EXTENSIONS (aktuell xlsx/xls)."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
