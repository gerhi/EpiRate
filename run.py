"""Einstiegspunkt – startet den Flask-Entwicklungsserver auf Port 5001."""

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Port 5001 statt 5000, da macOS AirPlay den Standardport belegt
    app.run(debug=app.config.get("FLASK_DEBUG", False), port=5001)
