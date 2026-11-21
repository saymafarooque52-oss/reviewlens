import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "cache.db"


def init_db() -> None:
    """Create the SQLite cache table if it does not exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_cache (
                text_hash TEXT PRIMARY KEY,
                analysis_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get_cached_analysis(text_hash: str) -> Optional[Dict[str, Any]]:
    """Return cached analysis dictionary for a given review text hash, or None."""
    if not text_hash:
        return None
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT analysis_json FROM review_cache WHERE text_hash = ?",
            (text_hash,),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def save_cached_analysis(text_hash: str, analysis: Dict[str, Any]) -> None:
    """Persist validated analysis JSON in SQLite keyed by review text hash."""
    if not text_hash:
        return
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO review_cache (text_hash, analysis_json)
            VALUES (?, ?)
            """,
            (text_hash, json.dumps(analysis)),
        )
        conn.commit()