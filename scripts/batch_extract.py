import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
from src.config import DB_PATH
from src.agents.extract_info import extract_and_save


def get_unextracted_pubmed_ids(limit=None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT s.source_id
        FROM sources s
        LEFT JOIN extracted_info e ON s.source_id = e.source_id
        WHERE e.source_id IS NULL
          AND s.source_id LIKE 'pubmed_%'
        ORDER BY s.source_id
    """)
    ids = [r["source_id"] for r in cur.fetchall()]
    conn.close()
    if limit:
        return ids[:limit]
    return ids


def main():
    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])

    pending = get_unextracted_pubmed_ids(limit)
    print("Pending PubMed extractions: {0}".format(len(pending)))

    success = 0
    for i, sid in enumerate(pending, 1):
        try:
            result = extract_and_save(sid)
            if "error" in result:
                print("  [{0}/{1}] {2} FAILED: {3}".format(i, len(pending), sid, result["error"]))
            else:
                sections = result.get("relevant_sections", [])
                print("  [{0}/{1}] {2} -> sections {3}".format(i, len(pending), sid, sections))
                success += 1
        except Exception as e:
            print("  [{0}/{1}] {2} EXCEPTION: {3}".format(i, len(pending), sid, e))

    print("\nSuccess: {0}/{1}".format(success, len(pending)))


if __name__ == "__main__":
    main()