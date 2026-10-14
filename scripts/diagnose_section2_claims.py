import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import sqlite3
from src.config import DB_PATH

SUSPECT_TERMS = [
    "toludesvenlafaxine",
    "LPM580153",
    "SERT",
    "IC50",
    "31.4",
    "586.7",
    "733.2",
    "forced swim",
    "tail suspension",
    "chronic unpredictable",
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("Searching all sources for suspect terms in Section 2 claims")
    print("=" * 70)
    cur.execute("SELECT source_id, title, raw_json FROM sources")
    rows = cur.fetchall()

    hits_by_term = {t: [] for t in SUSPECT_TERMS}

    for r in rows:
        blob = ((r["title"] or "") + " " + (r["raw_json"] or "")).lower()
        for term in SUSPECT_TERMS:
            if term.lower() in blob:
                hits_by_term[term].append(r["source_id"])

    for term, hits in hits_by_term.items():
        if hits:
            print("\n[{0}] -> {1} source(s):".format(term, len(hits)))
            for sid in hits[:8]:
                cur2 = conn.cursor()
                cur2.execute("SELECT title FROM sources WHERE source_id = ?", (sid,))
                row2 = cur2.fetchone()
                print("   {0} | {1}".format(sid, (row2["title"] or "")[:80]))
        else:
            print("\n[{0}] -> NO SOURCES CONTAIN THIS".format(term))

    conn.close()


if __name__ == "__main__":
    main()