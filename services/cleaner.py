import csv
import hashlib
import io
import re
from typing import Any, Dict, List

WORD_TO_NUM = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def strip_html(text: str) -> str:
    """Remove HTML tags like <b>...</b> and normalize whitespace."""
    cleaned = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_rating(raw_rating: str) -> Any:
    """Convert valid ratings (1-5 or word equivalents) to int; otherwise 'unknown'."""
    val = raw_rating.strip().lower()
    if val in WORD_TO_NUM:
        return WORD_TO_NUM[val]
    try:
        num = int(float(val))
        if 1 <= num <= 5:
            return num
    except ValueError:
        pass
    return "unknown"


def compute_text_hash(text: str) -> str:
    """Create a deterministic SHA-256 hash of normalized review text for deduplication and caching."""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_and_clean_csv(file_content: str) -> Dict[str, Any]:
    """
    Parse raw CSV text resiliently:
    - Handles unclosed trailing quotes (e.g., R009) without swallowing the next row
    - Handles extra columns on malformed rows (e.g., R022)
    - Flags empty reviews, normalizes ratings, strips HTML, and detects duplicates
    """
    lines = file_content.splitlines()
    if not lines:
        return {"reviews": [], "stats": {"total_rows": 0, "valid": 0, "skipped_empty": 0, "duplicates": 0}}

    # Skip header line
    data_lines = lines[1:]
    seen_hashes = {}
    cleaned_reviews: List[Dict[str, Any]] = []

    skipped_empty = 0
    duplicates = 0

    for line in data_lines:
        if not line.strip():
            continue

        # Fix unclosed trailing quote (like R009: `R009, Ceramic Coffee Mug (Set of 2),3,2026-10-08,"`)
        if line.count('"') % 2 != 0:
            line = line + '"'

        try:
            row = next(csv.reader(io.StringIO(line), skipinitialspace=True))
        except Exception:
            # Fallback split if CSV quoting is still broken
            row = [col.strip().strip('"') for col in line.split(",")]

        if len(row) < 4:
            continue

        review_id = row[0].strip()
        product = row[1].strip() or "Unknown Product"
        raw_rating = row[2].strip()
        date = row[3].strip()

        # Handle malformed extra columns (e.g., R022 has extra `,five, 2026-10-11,` before review text)
        raw_text = row[-1].strip() if len(row) >= 5 else ""
        cleaned_text = strip_html(raw_text)

        rating = normalize_rating(raw_rating)

        # Check empty review text (e.g., R005, R009)
        if not cleaned_text:
            skipped_empty += 1
            cleaned_reviews.append({
                "review_id": review_id,
                "product": product,
                "rating": rating,
                "date": date,
                "review_text": "",
                "text_hash": None,
                "status": "skipped_empty",
                "duplicate_of": None,
            })
            continue

        text_hash = compute_text_hash(cleaned_text)

        # Check duplicate review text (e.g., R015 duplicates R012)
        if text_hash in seen_hashes:
            duplicates += 1
            cleaned_reviews.append({
                "review_id": review_id,
                "product": product,
                "rating": rating,
                "date": date,
                "review_text": cleaned_text,
                "text_hash": text_hash,
                "status": "duplicate",
                "duplicate_of": seen_hashes[text_hash],
            })
            continue

        seen_hashes[text_hash] = review_id
        cleaned_reviews.append({
            "review_id": review_id,
            "product": product,
            "rating": rating,
            "date": date,
            "review_text": cleaned_text,
            "text_hash": text_hash,
            "status": "valid",
            "duplicate_of": None,
        })

    valid_count = sum(1 for r in cleaned_reviews if r["status"] == "valid")
    return {
        "reviews": cleaned_reviews,
        "stats": {
            "total_rows": len(cleaned_reviews),
            "valid": valid_count,
            "skipped_empty": skipped_empty,
            "duplicates": duplicates,
        },
    }