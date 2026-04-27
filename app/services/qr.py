"""QR-Code-Erzeugung – upload_folder wird explizit übergeben (kein Flask-Kontext in Threads)."""

import qrcode
from concurrent.futures import ThreadPoolExecutor


def generate_qr_code(url, token, upload_folder):
    """Erzeugt ein QR-Code-PNG und gibt den relativen Pfad für Templates zurück."""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    image_path = f"{upload_folder}/{token}.png"
    img.save(image_path)
    return f"qrcodes/{token}.png"


def generate_qr_codes_batch(urls_tokens, upload_folder):
    """Parallele QR-Erzeugung – max. 32 Threads, skaliert mit Batch-Größe."""
    def _generate_single(url_token_pair):
        url, token = url_token_pair
        return generate_qr_code(url, token, upload_folder)

    max_workers = min(32, len(urls_tokens))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(_generate_single, urls_tokens))
