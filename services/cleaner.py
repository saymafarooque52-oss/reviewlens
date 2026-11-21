import csv
import hashlib
import html
import io
import re
from typing import Any, Dict, List

WORD_RATINGS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5,
}


def normalize_rating(raw_rating: Any) -> Any:
    if raw_rating is None:
        return "unknown"
    val = str(raw_rating).strip().lower()
    if not val:
        return "unknown"
    if val in WORD_RATINGS:
        return WORD_RATINGS[val]
    try:
        num = int(float(val))
        return num if 1 <= num <= 5 else "unknown"
    except ValueError:
        return "unknown"


def clean_review_text(raw_text: Any) -> str:
    if raw_text is None:
        return ""
    text = html.unescape(str(raw_text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_text_hash(cleaned_text: str) -> str:
    normalized = cleaned_text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_and_clean_csv(file_bytes: bytes) -> Dict[str, Any]:
    try:
        content = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = file_bytes.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("Uploaded CSV file is empty or missing headers.")

    seen_hashes: Dict[str, str] = {}
    cleaned_rows: List[Dict[str, Any]] = []
    skipped_empty = 0
    duplicate_count = 0

    for idx, row in enumerate(reader, start=1):
        if not row or all((v is None or str(v).strip() == "") for v in row.values()):
            skipped_empty += 1
            continue

        review_id = str(row.get("review_id") or f"ROW-{idx}").strip()
        product = str(row.get("product") or "Unknown Product").strip()
        date_str = str(row.get("date") or "").strip()
        rating = normalize_rating(row.get("rating"))
        cleaned_text = clean_review_text(row.get("review_text"))

        if not cleaned_text:
            skipped_empty += 1
            cleaned_rows.append({
                "review_id": review_id,
                "product": product,
                "rating": rating,
                "date": date_str,
                "review_text": "",
                "status": "skipped_empty",
                "duplicate_of": None,
                "text_hash": None,
            })
            continue

        text_hash = compute_text_hash(cleaned_text)
        if text_hash in seen_hashes:
            duplicate_count += 1
            cleaned_rows.append({
                "review_id": review_id,
                "product": product,
                "rating": rating,
                "date": date_str,
                "review_text": cleaned_text,
                "status": "duplicate",
                "duplicate_of": seen_hashes[text_hash],
                "text_hash": text_hash,
            })
            continue

        seen_hashes[text_hash] = review_id
        cleaned_rows.append({
            "review_id": review_id,
            "product": product,
            "rating": rating,
            "date": date_str,
            "review_text": cleaned_text,
            "status": "valid",
            "duplicate_of": None,
            "text_hash": text_hash,
        })

    return {
        "rows": cleaned_rows,
        "stats": {
            "total_rows": len(cleaned_rows),
            "valid_unique": len(seen_hashes),
            "skipped_empty": skipped_empty,
            "duplicates": duplicate_count,
        },
    }