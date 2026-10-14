import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import sqlite3
from src.config import DB_PATH

SUSPECT_KEYWORDS = [
    "DOV", "216", "303",
    "Tesofensine", "NS2359", "NS-2359",
    "GSK372475", "GSK-372475",
    "Amitifadine", "EB-1020",
    "Bupropion", "Nomifensine",
    "Bicifadine", "Centanafadine",
]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("SOURCES THAT MENTION OTHER SNDRI-CLASS DRUGS")
    print("=" * 70)
    cur.execute("SELECT source_id, title, year FROM sources")
    for r in cur.fetchall():
        t = r["title"] or ""
        for kw in SUSPECT_KEYWORDS:
            if kw.lower() in t.lower():
                print("  [{0}] ({1}) {2}".format(kw, r["year"], r["title"][:90]))
                break

    print()
    print("=" * 70)
    print("SOURCES WHOSE TITLE DOES NOT MENTION JS1-1-01 BUT ARE ASSIGNED TO SECTION 3")
    print("=" * 70)
    cur.execute("SELECT source_id, extracted_json FROM extracted_info")
    for r in cur.fetchall():
        ex = json.loads(r["extracted_json"])
        sections = [str(s) for s in (ex.get("relevant_sections") or [])]
        if "3" in sections and not r["source_id"].startswith("ct_"):
            cur2 = conn.cursor()
            cur2.execute("SELECT title FROM sources WHERE source_id = ?", (r["source_id"],))
            row2 = cur2.fetchone()
            t = row2["title"] if row2 else "(no title)"
            has_js1 = "JS1" in t or "js1" in t.lower()
            print("  [{0}] {1} {2}".format(
                r["source_id"],
                "(MENTIONS JS1)" if has_js1 else "(NO JS1 MENTION)",
                t[:80]
            ))

    print()
    print("=" * 70)
    print("SOURCE COUNT BY SECTION")
    print("=" * 70)
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    cur.execute("SELECT extracted_json FROM extracted_info")
    for r in cur.fetchall():
        ex = json.loads(r["extracted_json"])
        for s in (ex.get("relevant_sections") or []):
            try:
                k = int(s)
                if k in counts:
                    counts[k] += 1
            except (ValueError, TypeError):
                pass
    for k in sorted(counts):
        print("  Section {0}: {1} sources".format(k, counts[k]))

    conn.close()


if __name__ == "__main__":
    main()