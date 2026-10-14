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
    CREATE TABLE IF NOT EXISTS search_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spec_id INTEGER,
        task_id TEXT,
        database_name TEXT,
        keywords TEXT,
        record_count INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS extracted_info (
        source_id TEXT PRIMARY KEY,
        extracted_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spec_id INTEGER,
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


def save_source(source: dict) -> bool:
    """Save one source record. Returns True on success."""
    try:
        year_value = source.get("year")
        if year_value is None:
            sd = source.get("start_date")
            if sd and isinstance(sd, str) and sd[:4].isdigit():
                year_value = int(sd[:4])

        conn = get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO sources
            (source_id, source_type, title, year, url, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                source.get("source_id"),
                source.get("source_type"),
                source.get("title"),
                year_value,
                source.get("url"),
                json.dumps(source, ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Failed to save source {0}: {1}".format(source.get("source_id"), e))
        return False


def save_many_sources(sources: list) -> int:
    """Save a list of source records. Returns count saved."""
    saved = 0
    for s in sources:
        if save_source(s):
            saved += 1
    return saved


def save_search_run(spec_id: int, task_id: str, database_name: str,
                    keywords: str, record_count: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO search_runs
        (spec_id, task_id, database_name, keywords, record_count)
        VALUES (?, ?, ?, ?, ?)""",
        (spec_id, task_id, database_name, keywords, record_count),
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_all_source_ids() -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source_id FROM sources")
    rows = [r["source_id"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_source(source_id: str) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT raw_json FROM sources WHERE source_id = ?", (source_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row["raw_json"])


def get_sources_by_type(source_type: str) -> list:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT raw_json FROM sources WHERE source_type = ?",
        (source_type,),
    )
    rows = [json.loads(r["raw_json"]) for r in cur.fetchall()]
    conn.close()
    return rows