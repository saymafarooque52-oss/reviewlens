import json
import sqlite3

DB_PATH = "cache.db"


def get_connection(db_path=DB_PATH):
    """Open SQLite database and create the cache table if it does not exist."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS review_cache (text_hash TEXT PRIMARY KEY, result_json TEXT)"
    )
    return conn


def get_cached_analysis(text_hash, db_path=DB_PATH):
    """Look up a review by its hash. Return the saved dictionary, or None if not found."""
    if not text_hash:
        return None

    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT result_json FROM review_cache WHERE text_hash = ?",
        (text_hash,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row[0])
    return None


def save_cached_analysis(text_hash, result, db_path=DB_PATH):
    """Save a review's AI analysis result into SQLite."""
    if not text_hash:
        return

    conn = get_connection(db_path)
    # Remove any old entry for this hash first, then insert the fresh result
    conn.execute("DELETE FROM review_cache WHERE text_hash = ?", (text_hash,))
    conn.execute(
        "INSERT INTO review_cache (text_hash, result_json) VALUES (?, ?)",
        (text_hash, json.dumps(result)),
    )
    conn.commit()
    conn.close()