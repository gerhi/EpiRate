"""Öffentliche Routen – Token-Login, Produktauswahl, Bewertungsformular, statische Seiten."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from app.db import get_db_connection
from app.auth import token_required
from app.services.pii import mask_pii, get_friendly_pii_name
import re

public_bp = Blueprint("public", __name__)


def _validate_and_activate_token(token_str):
    """Prüft Token gegen DB, setzt Session-Daten. Gibt (success, token_id) zurück."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, used FROM tokens WHERE token = %s", (token_str,))
            token_data = cur.fetchone()
            if token_data and not token_data["used"]:
                session["token_id"] = token_data["id"]
                session["token_str"] = token_str
                return True, token_data["id"]
            return False, None
    finally:
        conn.close()


@public_bp.route("/")
def index():
    # Direktlogin per URL-Parameter (?token=XYZ) – kommt z.B. vom QR-Code
    token = request.args.get("token")
    if token:
        success, _ = _validate_and_activate_token(token)
        if success:
            return redirect(url_for("public.products"))
        return render_template("login.html", token_invalid=True)
    return render_template("index.html")


@public_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        token = request.form["token"]
        success, _ = _validate_and_activate_token(token)
        if success:
            return redirect(url_for("public.products"))
        return render_template("login.html", token_invalid=True)
    return render_template("login.html")


@public_bp.route("/products")
@token_required
def products():
    token_id = session["token_id"]
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # started_at nur beim ersten Besuch setzen (Zeitstempel für Nutzungsdauer)
            cur.execute("SELECT started_at FROM tokens WHERE id = %s", (token_id,))
            token_record = cur.fetchone()
            if token_record and not token_record["started_at"]:
                cur.execute("UPDATE tokens SET started_at = %s WHERE id = %s", (datetime.now(), token_id))
                conn.commit()

            cur.execute("SELECT id, name FROM products ORDER BY name")
            all_products = cur.fetchall()
    finally:
        conn.close()
    return render_template("products.html", all_products=all_products)


@public_bp.route("/search_products")
@token_required
def search_products():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT id, name
                FROM products
                WHERE name LIKE %s
                ORDER BY
                    CASE
                        WHEN name = %s THEN 0
                        WHEN name LIKE %s THEN 1
                        ELSE 2
                    END,
                    name
                LIMIT 10;
            """
            cur.execute(sql, (f"%{query}%", query, f"{query}%"))
            products = [{"id": row["id"], "name": row["name"]} for row in cur.fetchall()]
    except Exception as e:
        return jsonify([])
    finally:
        conn.close()
    return jsonify(products)


@public_bp.route("/product_details/<int:product_id>")
@token_required
def product_details(product_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT manufacturer, category FROM products WHERE id = %s", (product_id,))
            product = cur.fetchone()
            if product:
                return jsonify({"manufacturer": product["manufacturer"], "category": product["category"]})
            return jsonify({"error": "Product not found"}), 404
    finally:
        conn.close()


@public_bp.route("/rate/<int:product_id>", methods=["GET", "POST"])
@token_required
def rate(product_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM products WHERE id = %s", (product_id,))
            product = cur.fetchone()
            product_name = product["name"] if product else "Unknown Product"
    finally:
        conn.close()

    if request.method == "POST":
        # Demografische Daten + 4 Bewertungskategorien aus dem Formular sammeln
        duration_of_usage = request.form.get("duration_of_usage")
        user_role = request.form.get("user_role")

        ratings = {
            "category1_rating": request.form.get("category1_rating", type=int),
            "category1_comment": request.form.get("category1_comment"),
            "category2_rating": request.form.get("category2_rating", type=int),
            "category2_comment": request.form.get("category2_comment"),
            "category3_rating": request.form.get("category3_rating", type=int),
            "category3_comment": request.form.get("category3_comment"),
            "category4_rating": request.form.get("category4_rating", type=int),
            "category4_comment": request.form.get("category4_comment"),
        }

        sql = """
            INSERT INTO ratings (token_id, product_id, duration_of_usage, role,
            category1_rating, category1_comment,
            category2_rating, category2_comment,
            category3_rating, category3_comment,
            category4_rating, category4_comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            session["token_id"], product_id, duration_of_usage, user_role,
            ratings["category1_rating"] or None, ratings["category1_comment"] or None,
            ratings["category2_rating"] or None, ratings["category2_comment"] or None,
            ratings["category3_rating"] or None, ratings["category3_comment"] or None,
            ratings["category4_rating"] or None, ratings["category4_comment"] or None,
        )

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
                # Token als verbraucht markieren – kann danach nicht mehr verwendet werden
                cur.execute(
                    "UPDATE tokens SET used = TRUE, used_at = %s WHERE id = %s",
                    (datetime.now(), session["token_id"]),
                )
                conn.commit()
        finally:
            conn.close()

        session.pop("token_id", None)
        session.pop("token_str", None)
        flash("Vielen Dank für Ihre Bewertung!", "success")
        return redirect(url_for("public.index"))

    return render_template("rate.html", product_id=product_id, product_name=product_name)


@public_bp.route("/check_comment", methods=["POST"])
@token_required
def check_comment():
    """Prüft Kommentare auf PII (Telefonnummern via Regex, Rest via NER-Modell)."""
    comment = request.json.get("comment", "")

    # Deutsche Telefonnummern-Muster (Festnetz + Mobil, mit/ohne Vorwahl)
    phone_patterns = [
        r"\+49\s?(\d{3,4})\s?(\d{6,8})",
        r"\+49\s?1[5-7]\d\s?(\d{7,8})",
        r"(?<!\d)0\d{2,4}\s?(\d{6,8})(?!\d)",
        r"(?<!\d)01[5-7]\d\s?(\d{7,8})(?!\d)",
        r"(?<!\d)\d{4,5}[\s\-/]?\d{6,8}(?!\d)",
        r"(?<!\d)\d{11}(?!\d)",
        r"(?<!\d)\d{10}(?!\d)",
    ]
    for pattern in phone_patterns:
        if re.search(pattern, comment):
            return jsonify({
                "status": "error",
                "message": "Der Kommentar könnte eine deutsche Telefon- oder Mobilnummer enthalten. Bitte überprüfen Sie Ihren Kommentar.",
            }), 400

    # Kurze Kommentare überspringen – NER-Modell braucht ausreichend Kontext
    if len(comment) < 10:
        return jsonify({"status": "success"})

    masked_comment, probabilities = mask_pii(comment, aggregate_redaction=False)

    if probabilities:
        pii_types = list(set([get_friendly_pii_name(key.split("_")[0]) for key in probabilities.keys()]))
        return jsonify({
            "status": "error",
            "message": "Der Kommentar könnte persönliche Informationen enthalten. Bitte überprüfen Sie Ihren Kommentar.",
            "masked_comment": masked_comment,
            "pii_probabilities": probabilities,
            "pii_types": pii_types,
        }), 400
    else:
        return jsonify({"status": "success"})


@public_bp.route("/about-project")
def about_project():
    return render_template("about_project.html")


@public_bp.route("/contact")
def contact_page():
    return render_template("contact.html")


@public_bp.route("/impressum")
def impressum():
    return render_template("impressum.html")


@public_bp.route("/datenschutz")
def datenschutz():
    return render_template("datenschutz.html")


