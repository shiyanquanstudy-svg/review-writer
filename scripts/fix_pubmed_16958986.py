import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from src.db.db_helper import get_conn

SOURCE_ID = "pubmed_16958986"


def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT extracted_json FROM extracted_info WHERE source_id = ?", (SOURCE_ID,))
    row = cur.fetchone()
    if row is None:
        print("Not found: {0}".format(SOURCE_ID))
        conn.close()
        return

    extracted = json.loads(row["extracted_json"])
    old = extracted.get("relevant_sections")
    extracted["relevant_sections"] = [2]
    extracted["notes"] = (
        "This is DOV 216,303, a different SNDRI-class drug, NOT JS1-1-01. "
        "It can serve as background for Section 2 (SNDRI class pharmacology), "
        "but MUST NOT be cited as evidence for JS1-1-01's development history."
    )

    cur.execute(
        "UPDATE extracted_info SET extracted_json = ? WHERE source_id = ?",
        (json.dumps(extracted, ensure_ascii=False), SOURCE_ID),
    )
    conn.commit()
    conn.close()

    print("Fixed {0}: {1} -> {2}".format(SOURCE_ID, old, extracted["relevant_sections"]))


if __name__ == "__main__":
    main()