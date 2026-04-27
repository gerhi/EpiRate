"""Datenexport – JSONL (alle Tabellen) und Excel (Token-Listen, Nutzungsdauer)."""

import io
import json
import tempfile
from datetime import datetime, timedelta

import pandas as pd

from app.db import get_db_connection


# Whitelist gegen SQL-Injection – nur diese Tabellen dürfen exportiert werden
ALLOWED_EXPORT_TABLES = {"ratings", "products", "tokens", "admins"}


def export_table_jsonl(table_name):
    """Exportiert eine komplette Tabelle als JSONL-Temp-Datei. Caller räumt Datei auf."""
    if table_name not in ALLOWED_EXPORT_TABLES:
        raise ValueError(f"Table '{table_name}' is not allowed for export")

    temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".jsonl")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            for row in rows:
                cleaned_row = {}
                for key, value in row.items():
                    if isinstance(value, datetime):
                        cleaned_row[key] = value.isoformat()
                    else:
                        cleaned_row[key] = value
                json.dump(cleaned_row, temp_file)
                temp_file.write("\n")
    finally:
        conn.close()

    temp_file.close()
    return temp_file.name


def build_tokens_excel(tokens_data, base_url):
    """Erzeugt eine Excel-Datei mit Token, URL, Erstelldatum und Gültigkeit."""
    df_data = []
    for token_row in tokens_data:
        token = token_row["token"]
        created_at = token_row["created_at"]
        if isinstance(created_at, str):
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        else:
            created_dt = created_at

        valid_until = created_dt + timedelta(days=90)
        df_data.append({
            "Token": token,
            "URL": f"{base_url}?token={token}",
            "Erstellt am": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "Gültig bis": valid_until.strftime("%Y-%m-%d %H:%M:%S"),
            "Erstellt von": token_row["created_by"],
        })

    df = pd.DataFrame(df_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Generated Tokens", index=False)
        worksheet = writer.sheets["Generated Tokens"]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            worksheet.column_dimensions[column_letter].width = min(max_length + 2, 50)
    output.seek(0)
    return output


def build_token_usage_excel(tokens_data):
    """Excel mit Nutzungsdauer pro Token (started_at → used_at in Sekunden)."""
    df_data = []
    for token_row in tokens_data:
        started_at = token_row["started_at"]
        used_at = token_row["used_at"]
        duration_seconds = "N/A"

        if started_at and used_at:
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at)
            if isinstance(used_at, str):
                used_at = datetime.fromisoformat(used_at)
            if isinstance(started_at, datetime) and isinstance(used_at, datetime):
                duration_seconds = (used_at - started_at).total_seconds()

        df_data.append({
            "Token": token_row["token"],
            "Started At": started_at.isoformat() if isinstance(started_at, datetime) else started_at,
            "Used At": used_at.isoformat() if isinstance(used_at, datetime) else used_at,
            "Usage Duration (seconds)": duration_seconds,
        })

    df = pd.DataFrame(df_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Token Usage Duration", index=False)
    output.seek(0)
    return output
