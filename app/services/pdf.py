"""PDF-Erzeugung – Token-Karten im A4-Format (4 Karten pro Seite, 2×2 Raster)."""

import io
import os
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def _draw_wrapped_text(c, text, x, y, max_width, font_name="Helvetica", font_size=7, leading_extra=1):
    """Manueller Zeilenumbruch, da reportlab kein auto-wrap bietet. Gibt y nach letzter Zeile zurück."""
    c.setFont(font_name, font_size)
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        if c.stringWidth(test, font_name, font_size) <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    line_height = font_size + leading_extra
    for line in lines:
        c.drawString(x, y, line)
        y -= line_height
    return y


def generate_tokens_pdf_bytes(tokens_data, base_url, upload_folder):
    """Generate a PDF with token cards and QR codes. Returns BytesIO."""
    first_token = tokens_data[0]
    created_at = first_token["created_at"]
    if isinstance(created_at, str):
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except Exception:
            created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    else:
        created_dt = created_at
    valid_until = created_dt + timedelta(days=90)

    text_erklaerung_1 = (
        "Dieser Token ist ein Einmal-Passwort mit dem Sie eine Produktbewertung abgeben können. "
        "Es können Hilfsmittel und technische Assistenzsysteme für Menschen mit Epilepsie bewertet werden."
    )
    text_erklaerung_2 = (
        "Scannen Sie einfach den QR-Code (z.B. mit der Handy-Kamera oder einer passenden App). "
        "Der Token ist bereits aktiviert und Sie können direkt mit der Bewertung starten."
    )
    base_url_display = base_url.replace("https://", "").replace("http://", "").strip("/")

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=A4)
    width, height = A4

    # Layout: 2×2 Raster, 4 Token-Karten pro A4-Seite
    tokens_per_page = 4
    margin = 12 * mm
    gap = 6 * mm
    card_height = (height - 2 * margin - gap) / 2
    card_width = (width - 2 * margin - gap) / 2
    text_margin = 6 * mm
    max_text_width = card_width - 2 * text_margin
    qr_size = 40 * mm

    for idx, token_row in enumerate(tokens_data):
        token = token_row["token"]

        position_on_page = idx % tokens_per_page
        if position_on_page == 0 and idx > 0:
            c.showPage()

        row = position_on_page // 2
        col = position_on_page % 2
        x_offset = margin + col * (card_width + gap)
        y_offset = height - margin - (row + 1) * card_height - row * gap

        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)
        c.rect(x_offset, y_offset, card_width, card_height)

        text_x = x_offset + text_margin
        text_y = y_offset + card_height - 5 * mm
        c.setFillColorRGB(0, 0, 0)

        c.setFont("Helvetica-Bold", 14)
        c.drawString(text_x, text_y, "Produktbewertung abgeben")
        text_y -= 5 * mm

        text_y = _draw_wrapped_text(c, text_erklaerung_1, text_x, text_y, max_text_width, "Helvetica", 10, leading_extra=0.5)
        text_y -= 3 * mm

        c.setFont("Helvetica", 10)
        c.drawString(text_x, text_y, "Ihr Token:")
        text_y -= 4 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(text_x, text_y, token)
        text_y -= 8 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, "So geht's!")
        text_y -= 4 * mm
        c.setFont("Helvetica", 10)
        c.drawString(text_x, text_y, f"1. {base_url_display} im Browser öffnen")
        text_y -= 3.5 * mm
        c.drawString(text_x, text_y, "2. Starten & Token eingeben")
        text_y -= 3.5 * mm
        c.drawString(text_x, text_y, "3. Produkt bewerten")
        text_y -= 8 * mm

        c.setFont("Helvetica-Bold", 10)
        c.drawString(text_x, text_y, "Die schnelle Alternative!")
        text_y -= 4 * mm
        c.setFont("Helvetica", 10)
        text_y = _draw_wrapped_text(c, text_erklaerung_2, text_x, text_y, max_text_width, "Helvetica", 10, leading_extra=0.5)
        text_y -= 4 * mm

        qr_path = f"{upload_folder}/{token}.png"
        qr_x = x_offset + (card_width - qr_size) / 2
        qr_y = y_offset + 10 * mm

        if os.path.exists(qr_path):
            try:
                img = ImageReader(qr_path)
                c.drawImage(img, qr_x, qr_y, width=qr_size, height=qr_size)
            except Exception:
                c.setStrokeColorRGB(0, 0, 0)
                c.rect(qr_x, qr_y, qr_size, qr_size)
                c.setFont("Helvetica", 5)
                c.drawString(qr_x + 8, qr_y + qr_size / 2 - 2, "QR Code")

        c.setFont("Helvetica", 10)
        footer_y = y_offset + 3 * mm
        footer_text = f"Einmal verwendbar, gültig bis {valid_until.strftime('%d.%m.%Y')}."
        if c.stringWidth(footer_text, "Helvetica", 5) > max_text_width:
            footer_text = f"Gültig bis {valid_until.strftime('%d.%m.%Y')}."
        c.drawString(text_x, footer_y, footer_text)

    c.save()
    output.seek(0)
    return output
