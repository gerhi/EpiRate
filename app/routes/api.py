"""REST-API – Produkt-Import, Rating-Export und Systemstatus (kein Auth, für interne Nutzung)."""

from flask import Blueprint, request, jsonify
from datetime import datetime

from app.db import get_db_connection

import pandas as pd

from app.utils import allowed_file

api_bp = Blueprint("api", __name__)


@api_bp.route("/import-products", methods=["POST"])
def import_products():
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file provided", "error_code": "NO_FILE"}), 400

    file = request.files["file"]
    if not file or not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Invalid file type. Please upload an Excel file (.xlsx or .xls)", "error_code": "INVALID_FILE_TYPE"}), 400

    import_stats = {"total": 0, "imported": 0, "updated": 0, "skipped": 0, "skip_reasons": [], "update_details": []}

    try:
        df = pd.read_excel(file)
        import_stats["total"] = len(df)

        required_columns = ["BASISID", "BEZEICHNUNG", "HERSTELLER", "KATEGORIE"]
        if not all(col in df.columns for col in required_columns):
            return jsonify({
                "status": "error",
                "message": "Missing required columns. Required: BASISID, BEZEICHNUNG, HERSTELLER, KATEGORIE",
                "error_code": "MISSING_COLUMNS",
                "required_columns": required_columns,
                "found_columns": df.columns.tolist(),
            }), 400

        df = df.fillna("")

        invalid_ids = df[~df["BASISID"].astype(str).str.match(r"^\d+$")]
        if not invalid_ids.empty:
            for _, row in invalid_ids.iterrows():
                import_stats["skip_reasons"].append({
                    "id": str(row["BASISID"]), "name": str(row["BEZEICHNUNG"]),
                    "reason": "Invalid ID format - must be a number",
                })
                import_stats["skipped"] += 1

        df = df[df["BASISID"].astype(str).str.match(r"^\d+$")]
        df["BASISID"] = df["BASISID"].astype(int)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                for _, row in df.iterrows():
                    if not all([row["BASISID"], row["BEZEICHNUNG"]]):
                        import_stats["skip_reasons"].append({
                            "id": str(row["BASISID"]), "name": str(row["BEZEICHNUNG"]),
                            "reason": "Missing ID or name",
                        })
                        import_stats["skipped"] += 1
                        continue

                    manufacturer = row["HERSTELLER"] if row["HERSTELLER"] else "MISSING"
                    category = row["KATEGORIE"] if row["KATEGORIE"] else "MISSING"

                    if not row["HERSTELLER"] or not row["KATEGORIE"]:
                        import_stats["skip_reasons"].append({
                            "id": str(row["BASISID"]), "name": str(row["BEZEICHNUNG"]),
                            "reason": "Missing manufacturer or category - using MISSING", "type": "warning",
                        })

                    cur.execute("SELECT id, name, manufacturer, category FROM products WHERE id = %s", (row["BASISID"],))
                    existing = cur.fetchone()

                    if existing:
                        changes = []
                        if existing["name"] != row["BEZEICHNUNG"]:
                            changes.append(f"Name: '{existing['name']}' → '{row['BEZEICHNUNG']}'")
                        if existing["manufacturer"] != manufacturer:
                            changes.append(f"Hersteller: '{existing['manufacturer']}' → '{manufacturer}'")
                        if existing["category"] != category:
                            changes.append(f"Kategorie: '{existing['category']}' → '{category}'")

                        if changes:
                            cur.execute("UPDATE products SET name=%s, manufacturer=%s, category=%s WHERE id=%s",
                                        (row["BEZEICHNUNG"], manufacturer, category, row["BASISID"]))
                            import_stats["update_details"].append({
                                "id": str(row["BASISID"]), "name": str(row["BEZEICHNUNG"]), "changes": changes,
                            })
                            import_stats["updated"] += 1
                        else:
                            import_stats["skip_reasons"].append({
                                "id": str(row["BASISID"]), "name": str(row["BEZEICHNUNG"]),
                                "reason": "Product already exists with identical properties", "type": "info",
                            })
                            import_stats["skipped"] += 1
                    else:
                        cur.execute("INSERT INTO products (id, name, manufacturer, category) VALUES (%s,%s,%s,%s)",
                                    (row["BASISID"], row["BEZEICHNUNG"], manufacturer, category))
                        import_stats["imported"] += 1
                conn.commit()
        finally:
            conn.close()

        parts = []
        if import_stats["imported"] > 0:
            parts.append(f"{import_stats['imported']} neu importiert")
        if import_stats["updated"] > 0:
            parts.append(f"{import_stats['updated']} aktualisiert")
        if import_stats["skipped"] > 0:
            parts.append(f"{import_stats['skipped']} übersprungen")

        return jsonify({
            "status": "success",
            "message": "Import abgeschlossen: " + ", ".join(parts) if parts else "Import abgeschlossen",
            "data": import_stats,
        }), 200

    except Exception:
        return jsonify({"status": "error", "message": "Error processing file", "error_code": "PROCESSING_ERROR"}), 500


@api_bp.route("/export-ratings", methods=["GET"])
def export_ratings():
    """Exportiert alle Bewertungen als JSON inkl. Übersetzung der Spalten ins Deutsche."""
    # Mapping-Tabellen für die deutsche Ausgabe
    USER_ROLE_DE = {
        "Person with epilepsy": "Person mit Epilepsie",
        "Specialist": "Fachkraft (Pflegende Person / Betreuer:in)",
        "Affiliated person": "An- und Zugehörige:r",
        "Doctor": "Arzt/Ärztin",
    }
    DURATION_DE = {
        "<4 weeks": "Weniger als 4 Wochen",
        "1-6 months": "1-6 Monate",
        "6-12 months": "7-12 Monate",
        ">1 years": "Mehr als 1 Jahr",
    }
    CATEGORY_RENAME = {
        "category1_rating": "benutzerfreundlichkeit_rating",
        "category1_comment": "benutzerfreundlichkeit_comment",
        "category2_rating": "wahrgenommener_nutzen_rating",
        "category2_comment": "wahrgenommener_nutzen_comment",
        "category3_rating": "zuverlaessigkeit_rating",
        "category3_comment": "zuverlaessigkeit_comment",
        "category4_rating": "gesamtbewertung_rating",
        "category4_comment": "gesamtbewertung_comment",
    }

    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # CTE mit ROW_NUMBER: nur die neueste Bewertung pro Token (Duplikate ausschließen)
                cur.execute("""
                    WITH ranked_ratings AS (
                        SELECT r.id as rating_id, r.created_at, r.duration_of_usage, r.role as user_role,
                            r.category1_rating, r.category1_comment, r.category2_rating, r.category2_comment,
                            r.category3_rating, r.category3_comment, r.category4_rating, r.category4_comment,
                            r.token_id, p.id as product_id, p.name as product_name, p.manufacturer, p.category,
                            t.token, t.created_at as token_created_at, t.started_at as token_started_at,
                            t.used_at as token_used_at, t.created_by as token_created_by,
                            ROW_NUMBER() OVER (PARTITION BY r.token_id ORDER BY r.created_at DESC) as rn
                        FROM ratings r LEFT JOIN products p ON r.product_id = p.id LEFT JOIN tokens t ON r.token_id = t.id
                    )
                    SELECT rating_id, created_at, duration_of_usage, user_role,
                        category1_rating, category1_comment, category2_rating, category2_comment,
                        category3_rating, category3_comment, category4_rating, category4_comment,
                        product_id, product_name, manufacturer, category, token,
                        token_created_at, token_started_at, token_used_at, token_created_by
                    FROM ranked_ratings WHERE rn = 1 ORDER BY created_at DESC
                """)
                ratings = cur.fetchall()
        finally:
            conn.close()

        cleaned = []
        for rating in ratings:
            row = {}
            for key, value in rating.items():
                if isinstance(value, datetime):
                    row[key] = value.isoformat()
                elif key == "user_role":
                    row[key] = USER_ROLE_DE.get(value, value)
                elif key == "duration_of_usage":
                    row[key] = DURATION_DE.get(value, value)
                elif key in CATEGORY_RENAME:
                    row[CATEGORY_RENAME[key]] = value
                else:
                    row[key] = value
            cleaned.append(row)

        return jsonify({
            "status": "success",
            "total_ratings": len(cleaned),
            "export_timestamp": datetime.now().isoformat(),
            "categories": {"1": "Benutzerfreundlichkeit", "2": "Wahrgenommener Nutzen", "3": "Zuverlässigkeit", "4": "Gesamtbewertung"},
            "data": cleaned,
        }), 200

    except Exception:
        return jsonify({"status": "error", "message": "Error exporting ratings", "error_code": "EXPORT_ERROR"}), 500


@api_bp.route("/status", methods=["GET"])
def status():
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total FROM tokens")
                total_tokens = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as used FROM tokens WHERE used = TRUE")
                used_tokens = cur.fetchone()["used"]
                cur.execute("SELECT COUNT(*) as total FROM products")
                total_products = cur.fetchone()["total"]
                cur.execute("SELECT COUNT(*) as total FROM ratings")
                total_ratings = cur.fetchone()["total"]
        finally:
            conn.close()

        return jsonify({
            "status": "success", "system_status": "operational",
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_tokens": total_tokens, "used_tokens": used_tokens,
                "unused_tokens": total_tokens - used_tokens,
                "total_products": total_products, "total_ratings": total_ratings,
            },
        }), 200

    except Exception:
        return jsonify({"status": "error", "message": "Error retrieving system status", "error_code": "STATUS_ERROR"}), 500
