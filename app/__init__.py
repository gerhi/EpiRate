"""App-Factory – erzeugt und konfiguriert die Flask-Anwendung."""

import os
from flask import Flask
from config import Config


def create_app():
    """Factory-Funktion: Konfiguration laden, Verzeichnisse anlegen, Blueprints registrieren."""
    app = Flask(
        __name__,
        # Templates und Static liegen eine Ebene über dem app-Package
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static"),
    )
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER_EXCEL"], exist_ok=True)

    from app.translations import get_translation
    from datetime import datetime

    @app.context_processor
    def inject_globals():
        """Stellt `now` und `translate` in allen Jinja2-Templates bereit."""
        return {"now": datetime.now, "translate": get_translation}

    from app.routes import register_blueprints
    register_blueprints(app)

    return app
