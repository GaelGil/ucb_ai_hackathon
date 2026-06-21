from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from app.models import SourceType


def source_type_from_filename(filename: str | None, fallback: SourceType = SourceType.TEXT) -> SourceType:
    if not filename:
        return fallback
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        return SourceType.CSV
    if suffix == ".txt":
        return SourceType.TXT
    if suffix == ".pdf":
        return SourceType.PDF
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}:
        return SourceType.IMAGE
    return fallback


def parse_text_items(text: str, source_type: SourceType) -> list[str]:
    if source_type == SourceType.CSV:
        return parse_csv_items(text)
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_csv_items(text: str) -> list[str]:
    rows = list(csv.DictReader(StringIO(text)))
    if rows and rows[0]:
        preferred_keys = ["text", "sentence", "sentences", "utterance", "content"]
        selected_key = next((key for key in preferred_keys if key in rows[0]), None)
        if selected_key is None:
            selected_key = next(iter(rows[0].keys()))
        return [row[selected_key].strip() for row in rows if row.get(selected_key, "").strip()]

    reader = csv.reader(StringIO(text))
    values: list[str] = []
    for row in reader:
        first = next((cell.strip() for cell in row if cell.strip()), "")
        if first:
            values.append(first)
    return values
