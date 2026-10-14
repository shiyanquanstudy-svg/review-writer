import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from src.config import DB_PATH


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check current schema
    cur.execute("PRAGMA table_info(drafts)")
    cols = [row[1] for row in cur.fetchall()]
    print("Current drafts columns:", cols)

    # Drop and recreate with correct schema
    cur.execute("DROP TABLE IF EXISTS drafts")
    cur.execute("""
        CREATE TABLE drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spec_id INTEGER,
            section_number INTEGER,
            content TEXT,
            citations_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    cur.execute("PRAGMA table_info(drafts)")
    new_cols = [row[1] for row in cur.fetchall()]
    print("New drafts columns:", new_cols)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()