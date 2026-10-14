import sqlite3
import json
from src.config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS review_specs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        instruction TEXT NOT NULL,
        spec_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sources (
        source_id TEXT PRIMARY KEY,
        source_type TEXT,
        title TEXT,
        year INTEGER,
        url TEXT,
        raw_json TEXT
    );
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        review_id INTEGER,
        section_number INTEGER,
        content TEXT,
        citations_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()


def save_spec(instruction: str, spec_dict: dict) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO review_specs (instruction, spec_json) VALUES (?, ?)",
        (instruction, json.dumps(spec_dict, ensure_ascii=False)),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def save_source(source: dict):
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO sources
        (source_id, source_type, title, year, url, raw_json)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            source["source_id"],
            source.get("source_type"),
            source.get("title"),
            source.get("year"),
            source.get("url"),
            json.dumps(source, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()