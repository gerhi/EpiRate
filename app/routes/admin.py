"""Admin-Backend – Token-Verwaltung, Statistiken, Produkt-Import, Exporte, Nutzerverwaltung."""

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app, after_this_request
from datetime import datetime, timedelta

from app.db import get_db_connection
from app.auth import admin_required, login_required, hash_password, verify_password
from app.translations import get_translation
from app.utils import allowed_file
from app.services.tokens import generate_tokens, insert_tokens_batch
from app.services.qr import generate_qr_codes_batch
from app.services.pdf import generate_tokens_pdf_bytes
from app.services.export import export_table_jsonl, build_tokens_excel, build_token_usage_excel

import pandas as pd

admin_bp = Blueprint("admin", __name__)


# ---------- Auth ----------

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT password, role FROM admins WHERE username = %s", (username,))
                admin_data = cur.fetchone()
        finally:
            conn.close()
        if admin_data and verify_password(admin_data["password"], password, username=username):
            session["admin_logged_in"] = True
            session["admin_role"] = admin_data["role"]
            session["admin_username"] = username
            return redirect(url_for("admin.dashboard"))
        else:
            flash("Anmeldung fehlgeschlagen. Bitte überprüfen Sie Benutzername und Passwort.", "danger")
    return render_template("admin/login.html")


@admin_bp.route("/")
@login_required
def dashboard():
    admin_role = session.get("admin_role", "MANAGER")
    return render_template("admin/dashboard.html", admin_role=admin_role)


@admin_bp.route("/logout")
@login_required
def logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_role", None)
    session.pop("admin_username", None)
    return redirect(url_for("admin.login"))


# ---------- Tokens ----------

@admin_bp.route("/generate-tokens", methods=["GET", "POST"])
@login_required
def generate_tokens_page():
    if request.method == "POST":
        try:
            num_tokens = int(request.form.get("num_tokens", 0))
        except (ValueError, TypeError):
            flash("Bitte eine gültige Zahl eingeben.", "error")
            return render_template("admin/generate_tokens.html")
        if num_tokens < 1 or num_tokens > 10000:
            flash("Anzahl der Tokens muss zwischen 1 und 10.000 liegen.", "error")
            return render_template("admin/generate_tokens.html")

        tokens_list = generate_tokens(num_tokens)
        admin_username = session.get("admin_username")
        insert_tokens_batch(tokens_list, admin_username)

        created_at_batch = datetime.now()
        valid_until_batch = created_at_batch + timedelta(days=90)  # Tokens verfallen nach 90 Tagen

        base_url = request.host_url.rstrip("/")
        urls = [f"{base_url}?token={t}" for t in tokens_list]
        # upload_folder explizit übergeben, da QR-Erzeugung im ThreadPool läuft (kein Flask-Kontext)
        qr_paths = generate_qr_codes_batch(list(zip(urls, tokens_list)), current_app.config["UPLOAD_FOLDER"])

        batch_timestamp_str = created_at_batch.strftime("%Y-%m-%d %H:%M:%S")
        session["export_batch_timestamp"] = batch_timestamp_str
        session["export_batch_id"] = created_at_batch.strftime("%Y-%m-%d")

        flash(f"{num_tokens} Tokens erfolgreich generiert!", "success")
        return render_template(
            "admin/token_list.html",
            tokens=zip(tokens_list, urls, qr_paths),
            created_at=created_at_batch,
            valid_until=valid_until_batch,
            batch_timestamp=batch_timestamp_str,
        )
    return render_template("admin/generate_tokens.html")


# ---------- Stats ----------

@admin_bp.route("/stats")
@login_required
def stats():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM tokens")
            total_tokens = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as used FROM tokens WHERE used = TRUE")
            used_tokens = cur.fetchone()["used"]

            cur.execute("SELECT created_at FROM tokens ORDER BY created_at DESC LIMIT 1")
            r = cur.fetchone()
            last_created_at = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r else None

            cur.execute("SELECT used_at FROM tokens WHERE used = TRUE ORDER BY used_at DESC LIMIT 1")
            r = cur.fetchone()
            last_used_at = r["used_at"].strftime("%Y-%m-%d %H:%M:%S") if r else None

            # Nutzungsstatistik der letzten 7 Tage (erstellt vs. eingelöst)
            today = datetime.now()
            usage_data = []
            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                formatted = date.strftime("%Y-%m-%d")
                cur.execute("SELECT COUNT(*) as count FROM tokens WHERE DATE(created_at) = %s", (formatted,))
                created_count = cur.fetchone()["count"]
                cur.execute("SELECT COUNT(*) as count FROM tokens WHERE DATE(used_at) = %s", (formatted,))
                used_count = cur.fetchone()["count"]
                usage_data.append({"date": formatted, "created": created_count, "used": used_count})

            cur.execute("""
                SELECT p.name,
                    AVG(r.category1_rating) as avg_cat1, AVG(r.category2_rating) as avg_cat2,
                    AVG(r.category3_rating) as avg_cat3, AVG(r.category4_rating) as avg_cat4
                FROM products p LEFT JOIN ratings r ON p.id = r.product_id GROUP BY p.id
            """)
            avg_ratings = cur.fetchall()

            cur.execute("""
                SELECT r.id, t.token, r.created_at, p.name as product_name,
                       r.category1_rating, r.category2_rating, r.category3_rating, r.category4_rating
                FROM ratings r JOIN tokens t ON r.token_id = t.id JOIN products p ON r.product_id = p.id
                ORDER BY r.created_at DESC LIMIT 100
            """)
            recent_ratings = cur.fetchall()

            cur.execute("SELECT token, created_at, created_by FROM tokens ORDER BY created_at DESC LIMIT 100")
            recent_tokens = cur.fetchall()

            cur.execute("""
                SELECT created_by,
                       COUNT(*) as total_tokens,
                       SUM(CASE WHEN used = TRUE THEN 1 ELSE 0 END) as used_tokens,
                       (SUM(CASE WHEN used = TRUE THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as usage_percentage
                FROM tokens WHERE created_by IS NOT NULL GROUP BY created_by ORDER BY usage_percentage DESC
            """)
            token_usage_by_user = cur.fetchall()
    finally:
        conn.close()

    return render_template(
        "admin/stats.html",
        total_tokens=total_tokens, used_tokens=used_tokens,
        last_created_at=last_created_at, last_used_at=last_used_at,
        usage_data=usage_data, avg_ratings=avg_ratings,
        recent_ratings=recent_ratings, recent_tokens=recent_tokens,
        token_usage_by_user=token_usage_by_user,
    )


# ---------- Exports ----------

@admin_bp.route("/export/<table_name>")
@admin_required
def export_table(table_name):
    allowed_tables = ["ratings", "products", "tokens"]
    if table_name not in allowed_tables:
        flash("Ungültiger Tabellenname.", "danger")
        return redirect(url_for("admin.dashboard"))

    try:
        filepath = export_table_jsonl(table_name)

        # Temp-Datei nach dem Senden automatisch aufräumen
        @after_this_request
        def remove_file(response):
            try:
                os.unlink(filepath)
            except Exception:
                pass
            return response

        return send_file(filepath, mimetype="application/json", as_attachment=True, download_name=f"{table_name}_export.jsonl")
    except Exception as e:
        flash(f"Error during export: {str(e)}", "danger")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/export-page")
@login_required
def export_page():
    return render_template("admin/export.html")


@admin_bp.route("/export-generated-tokens-excel")
@login_required
def export_tokens_excel():
    batch_timestamp_str = request.args.get("batch_time") or session.get("export_batch_timestamp")
    admin_username = session.get("admin_username")

    if not batch_timestamp_str:
        flash("Keine Token-Batch gefunden. Bitte generieren Sie zuerst Tokens.", "warning")
        return redirect(url_for("admin.generate_tokens_page"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Batch-Tokens anhand Zeitfenster (±30s) identifizieren
            batch_time = datetime.strptime(batch_timestamp_str, "%Y-%m-%d %H:%M:%S")
            cur.execute("""
                SELECT token, created_at, created_by FROM tokens
                WHERE created_by = %s AND created_at >= %s AND created_at <= %s
                ORDER BY created_at DESC
            """, (admin_username, batch_time - timedelta(seconds=30), batch_time + timedelta(seconds=30)))
            tokens_data = cur.fetchall()
    except Exception as e:
        flash(f"Fehler beim Laden der Token-Daten: {str(e)}", "danger")
        return redirect(url_for("admin.generate_tokens_page"))
    finally:
        conn.close()

    if not tokens_data:
        flash("Keine Tokens für diesen Zeitstempel gefunden.", "warning")
        return redirect(url_for("admin.generate_tokens_page"))

    base_url = request.host_url.rstrip("/")
    output = build_tokens_excel(tokens_data, base_url)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"generated_tokens_{timestamp}.xlsx")


@admin_bp.route("/export-token-usage-duration")
@login_required
def export_token_usage():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT token, started_at, used_at FROM tokens")
            tokens_data = cur.fetchall()
    finally:
        conn.close()

    output = build_token_usage_excel(tokens_data)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     as_attachment=True, download_name=f"token_usage_duration_{timestamp}.xlsx")


@admin_bp.route("/generate-tokens-pdf")
@login_required
def generate_tokens_pdf():
    batch_timestamp_str = request.args.get("batch_time") or session.get("export_batch_timestamp")
    admin_username = session.get("admin_username")

    if not batch_timestamp_str:
        flash("Keine Token-Batch gefunden. Bitte generieren Sie zuerst Tokens.", "warning")
        return redirect(url_for("admin.generate_tokens_page"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            batch_time = datetime.strptime(batch_timestamp_str, "%Y-%m-%d %H:%M:%S")
            cur.execute("""
                SELECT token, created_at, created_by FROM tokens
                WHERE created_by = %s AND created_at >= %s AND created_at <= %s
                ORDER BY created_at DESC
            """, (admin_username, batch_time - timedelta(seconds=30), batch_time + timedelta(seconds=30)))
            tokens_data = cur.fetchall()
    except Exception as e:
        flash(f"Fehler beim Laden der Token-Daten: {str(e)}", "danger")
        return redirect(url_for("admin.generate_tokens_page"))
    finally:
        conn.close()

    if not tokens_data:
        flash("Keine Tokens für diesen Zeitstempel gefunden.", "warning")
        return redirect(url_for("admin.generate_tokens_page"))

    base_url = request.host_url.rstrip("/")
    output = generate_tokens_pdf_bytes(tokens_data, base_url, current_app.config["UPLOAD_FOLDER"])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(output, mimetype="application/pdf", as_attachment=True, download_name=f"tokens_{timestamp}.pdf")


# ---------- Admin management ----------

@admin_bp.route("/list-admins")
@admin_required
def list_admins():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role FROM admins")
            admins = cur.fetchall()
    finally:
        conn.close()
    return render_template("admin/list_admins.html", admins=admins)


@admin_bp.route("/delete-admin/<int:admin_id>", methods=["POST"])
@admin_required
def delete_admin(admin_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Mindestens ein Admin muss immer existieren
            cur.execute("SELECT COUNT(*) as count FROM admins")
            if cur.fetchone()["count"] <= 1:
                flash("Der letzte Administrator kann nicht gelöscht werden.", "danger")
                return redirect(url_for("admin.list_admins"))
            cur.execute("DELETE FROM admins WHERE id = %s", (admin_id,))
            conn.commit()
            flash("Administrator erfolgreich gelöscht.", "success")
    finally:
        conn.close()
    return redirect(url_for("admin.list_admins"))


@admin_bp.route("/create-admin", methods=["GET", "POST"])
@admin_required
def create_admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        hashed_password = hash_password(password)

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM admins WHERE username = %s", (username,))
                if cur.fetchone()["cnt"] > 0:
                    flash("Benutzername existiert bereits.", "danger")
                else:
                    cur.execute("INSERT INTO admins (username, password, role) VALUES (%s, %s, %s)",
                                (username, hashed_password, role))
                    conn.commit()
                    flash("Neuer Administrator erfolgreich erstellt.", "success")
        finally:
            conn.close()
        return redirect(url_for("admin.create_admin"))
    return render_template("admin/create_admin.html")


@admin_bp.route("/reset-password/<int:admin_id>", methods=["GET", "POST"])
@admin_required
def reset_password(admin_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, role FROM admins WHERE id = %s", (admin_id,))
            admin = cur.fetchone()
            if not admin:
                flash("Administrator nicht gefunden.", "danger")
                return redirect(url_for("admin.list_admins"))

            if request.method == "POST":
                new_password = request.form["new_password"]
                confirm_password = request.form["confirm_password"]
                if not new_password or len(new_password) < 6:
                    flash("Passwort muss mindestens 6 Zeichen lang sein.", "danger")
                elif new_password != confirm_password:
                    flash("Passwörter stimmen nicht überein.", "danger")
                else:
                    hashed_password = hash_password(new_password)
                    cur.execute("UPDATE admins SET password = %s WHERE id = %s", (hashed_password, admin_id))
                    conn.commit()
                    flash(f'Passwort für Administrator "{admin["username"]}" wurde erfolgreich zurückgesetzt.', "success")
                    return redirect(url_for("admin.list_admins"))
    finally:
        conn.close()
    return render_template("admin/reset_password.html", admin=admin)


# ---------- Products ----------

@admin_bp.route("/manage-products", methods=["GET", "POST"])
@login_required
def manage_products():
    message = None
    products = []
    admin_role = session.get("admin_role", "MANAGER")
    import_stats = {"total": 0, "imported": 0, "updated": 0, "skipped": 0, "skip_reasons": [], "update_details": []}

    if request.method == "POST":
        if "file" in request.files:
            file = request.files["file"]
            if file and allowed_file(file.filename):
                try:
                    df = pd.read_excel(file)
                    import_stats["total"] = len(df)
                    required_columns = ["BASISID", "BEZEICHNUNG", "HERSTELLER", "KATEGORIE"]
                    if not all(col in df.columns for col in required_columns):
                        raise ValueError(get_translation("Missing required columns. Required: BASISID, BEZEICHNUNG, HERSTELLER, KATEGORIE"))

                    df = df.fillna("")
                    invalid_ids = df[~df["BASISID"].astype(str).str.match(r"^\d+$")]
                    if not invalid_ids.empty:
                        for _, row in invalid_ids.iterrows():
                            import_stats["skip_reasons"].append(
                                f"ID '{row['BASISID']}' ({row['BEZEICHNUNG']}): {get_translation('Invalid ID format - must be a number')}")
                            import_stats["skipped"] += 1

                    df = df[df["BASISID"].astype(str).str.match(r"^\d+$")]
                    df["BASISID"] = df["BASISID"].astype(int)

                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cur:
                            for _, row in df.iterrows():
                                if not all([row["BASISID"], row["BEZEICHNUNG"]]):
                                    import_stats["skip_reasons"].append(f"ID {row['BASISID']}: {get_translation('Missing ID or name')}")
                                    import_stats["skipped"] += 1
                                    continue

                                manufacturer = row["HERSTELLER"] if row["HERSTELLER"] else "MISSING"
                                category = row["KATEGORIE"] if row["KATEGORIE"] else "MISSING"

                                if not row["HERSTELLER"] or not row["KATEGORIE"]:
                                    import_stats["skip_reasons"].append(
                                        f"ID {row['BASISID']} ({row['BEZEICHNUNG']}): "
                                        f"{get_translation('Missing manufacturer or category - using MISSING')}")

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
                                        import_stats["update_details"].append(
                                            f"ID {row['BASISID']} ({row['BEZEICHNUNG']}): " + ", ".join(changes))
                                        import_stats["updated"] += 1
                                    else:
                                        import_stats["skip_reasons"].append(
                                            f"ID {row['BASISID']} ({row['BEZEICHNUNG']}): "
                                            + get_translation("Product already exists with identical properties"))
                                        import_stats["skipped"] += 1
                                else:
                                    cur.execute("INSERT INTO products (id, name, manufacturer, category) VALUES (%s,%s,%s,%s)",
                                                (row["BASISID"], row["BEZEICHNUNG"], manufacturer, category))
                                    import_stats["imported"] += 1
                            conn.commit()

                        parts = []
                        if import_stats["imported"] > 0:
                            parts.append(f"{import_stats['imported']} neu importiert")
                        if import_stats["updated"] > 0:
                            parts.append(f"{import_stats['updated']} aktualisiert")
                        if import_stats["skipped"] > 0:
                            parts.append(f"{import_stats['skipped']} übersprungen")

                        message = {"type": "success", "text": "Import abgeschlossen: " + ", ".join(parts) if parts else "Import abgeschlossen"}

                        all_details = []
                        if import_stats["update_details"]:
                            all_details.append("=== Aktualisierte Produkte ===")
                            all_details.extend(import_stats["update_details"])
                        if import_stats["skip_reasons"]:
                            if all_details:
                                all_details.append("")
                            all_details.append("=== Übersprungene Produkte ===")
                            all_details.extend(import_stats["skip_reasons"])
                        if all_details:
                            message["details"] = all_details
                    except Exception as e:
                        message = {"type": "danger", "text": f'{get_translation("Error during import")}: {str(e)}'}
                    finally:
                        conn.close()
                except Exception as e:
                    message = {"type": "danger", "text": f'{get_translation("Error processing file")}: {str(e)}'}
            else:
                message = {"type": "danger", "text": get_translation("Invalid file type. Please upload an Excel file (.xlsx or .xls)")}

        elif "delete_product" in request.form:
            product_id = request.form["delete_product"]
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) as count FROM ratings WHERE product_id = %s", (product_id,))
                    if cur.fetchone()["count"] > 0:
                        message = {"type": "danger", "text": "Produkte mit Bewertungen können nicht gelöscht werden."}
                    else:
                        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
                        conn.commit()
                        message = {"type": "success", "text": "Produkt erfolgreich gelöscht."}
            finally:
                conn.close()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.*, COUNT(r.id) as rating_count
                FROM products p LEFT JOIN ratings r ON p.id = r.product_id
                GROUP BY p.id ORDER BY p.id
            """)
            products = cur.fetchall()
    finally:
        conn.close()

    return render_template("admin/manage_products.html", products=products, message=message, admin_role=admin_role)
