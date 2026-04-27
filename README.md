# EpiRate

Bewertungsplattform für Hilfsmittel und technische Assistenzsysteme bei Epilepsie.

Entwickelt im Rahmen des BMBF-geförderten Forschungsprojektes **EXTENSIBLE**.

## Funktionen

- **Token-basierte Bewertungen** – Anonyme Produktbewertungen über Einmal-Tokens (QR-Code oder manuelle Eingabe)
- **PII-Erkennung** – Automatische Erkennung persönlicher Daten in Kommentaren (ML-basiert via [piiranha](https://huggingface.co/iiiorg/piiranha-v1-detect-personal-information))
- **Admin-Dashboard** – Token-Verwaltung, Statistiken, Produktimport (Excel), Datenexport
- **PDF-/Excel-Export** – Token-Karten als druckfertige PDFs, Bewertungsdaten als Excel/JSONL
- **REST-API** – Endpoints für Produktimport, Bewertungsexport und System-Status

## Voraussetzungen

- Python 3.10+
- MySQL/MariaDB-Datenbank
- (Optional) CUDA-fähige GPU für schnellere PII-Erkennung

## Installation

```bash
# Repository klonen (URL nach Erstellung des Repos anpassen)
git clone https://github.com/ORGANISATION/bethel.git
cd bethel

# Virtual Environment erstellen und aktivieren
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Konfiguration

Erstelle eine `.env`-Datei im Projektverzeichnis (siehe `.env.example`):

```env
# Datenbank
MYSQL_HOST=localhost
MYSQL_USER=your_db_user
MYSQL_PASSWORD=your_db_password
MYSQL_DB=your_db_name

# Flask
SECRET_KEY=change-me-to-a-random-secret-key
FLASK_DEBUG=false
```

> **Wichtig:** Die `.env`-Datei enthält Zugangsdaten und darf **nicht** ins Repository committed werden (ist in `.gitignore` ausgeschlossen).

## Datenbank

Die Anwendung erwartet folgende MySQL-Tabellen:

```sql
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    role ENUM('ADMIN', 'MANAGER') NOT NULL DEFAULT 'MANAGER'
);

CREATE TABLE tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token VARCHAR(8) NOT NULL UNIQUE,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    used_at TIMESTAMP NULL,
    created_by VARCHAR(255) NULL
);

CREATE TABLE products (
    id INT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    manufacturer VARCHAR(255) DEFAULT 'MISSING',
    category VARCHAR(255) DEFAULT 'MISSING'
);

CREATE TABLE ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    token_id INT NOT NULL,
    product_id INT NOT NULL,
    duration_of_usage VARCHAR(50),
    role VARCHAR(100),
    category1_rating INT,
    category1_comment TEXT,
    category2_rating INT,
    category2_comment TEXT,
    category3_rating INT,
    category3_comment TEXT,
    category4_rating INT,
    category4_comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (token_id) REFERENCES tokens(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

Erstelle einen initialen Admin-Benutzer:

```bash
# Passwort-Hash generieren (werkzeug/bcrypt)
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('admin'))"
```

```sql
-- Den generierten Hash einsetzen:
INSERT INTO admins (username, password, role)
VALUES ('admin', '<hash-aus-dem-vorherigen-schritt>', 'ADMIN');
```

> **Hinweis:** Bestehende SHA-256-Hashes werden beim Login weiterhin akzeptiert (Abwärtskompatibilität). Neue Passwörter werden automatisch sicher mit werkzeug/pbkdf2 gehasht.

## Starten

```bash
source .venv/bin/activate
python run.py
```

Die Anwendung ist unter `http://localhost:5001` erreichbar.

## Projektstruktur

```
bethel/
├── run.py                  # Einstiegspunkt
├── config.py               # Konfiguration aus .env
├── app/
│   ├── __init__.py         # App-Factory (create_app)
│   ├── db.py               # Datenbankverbindung
│   ├── auth.py             # Authentifizierung & Decorators
│   ├── translations.py     # Deutsche Übersetzungen
│   ├── routes/
│   │   ├── public.py       # Öffentliche Seiten (Login, Bewertung, etc.)
│   │   ├── admin.py        # Admin-Bereich (/admin/*)
│   │   └── api.py          # REST-API (/api/*)
│   └── services/
│       ├── tokens.py       # Token-Generierung
│       ├── qr.py           # QR-Code-Erzeugung
│       ├── pdf.py          # PDF-Generierung
│       ├── pii.py          # PII-Erkennung (Lazy Loading)
│       └── export.py       # Excel-/JSONL-Export
├── templates/              # Jinja2-Templates
├── static/                 # CSS, Bilder, Fonts
├── requirements.txt
├── .env.example
└── .gitignore
```

## Bewertungskategorien

| Nr. | Kategorie | Beschreibung |
|-----|-----------|-------------|
| 1 | Benutzerfreundlichkeit | Intuitivität, Lernkurve, Handhabung |
| 2 | Wahrgenommener Nutzen | Funktionserfüllung, Erwartungen |
| 3 | Zuverlässigkeit | Verarbeitungsqualität, Konsistenz |
| 4 | Gesamtbewertung | Gesamteindruck des Produkts |

## Technologie-Stack

| Komponente | Technologie |
|-----------|-------------|
| Backend | Flask 3.0 |
| Datenbank | MySQL (PyMySQL) |
| PII-Erkennung | Hugging Face Transformers + PyTorch |
| PDF-Erzeugung | ReportLab |
| Excel-Import/Export | pandas + openpyxl |
| QR-Codes | qrcode + Pillow |
| Frontend | Bootstrap 4, jQuery, Select2 |

## Förderung

Gefördert vom Bundesministerium für Bildung und Forschung (BMBF) im Rahmen des DATIpilot-Programms.
