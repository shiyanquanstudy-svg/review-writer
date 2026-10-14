import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import json

# 强制走 db_helper
from src.db.db_helper import get_conn
from src.agents.extract_info import extract_and_save


def main():
    print("USE_SUPABASE:", os.getenv("USE_SUPABASE", "false"))

    conn = get_conn()
    cur = conn.cursor()

    # 拿一条 pubmed_ 源
    cur.execute("""
        SELECT s.source_id FROM sources s
        LEFT JOIN extracted_info e ON s.source_id = e.source_id
        WHERE e.source_id IS NULL AND s.source_id LIKE 'pubmed_%'
        ORDER BY s.source_id
        LIMIT 1
    """)
    row = cur.fetchone()
    conn.close()

    if row is None:
        print("No pending pubmed source found.")
        return

    sid = row["source_id"]
    print("Testing source:", sid)

    # 试提取
    try:
        result = extract_and_save(sid)
        print("extract_and_save returned:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        import traceback
        print("EXCEPTION:")
        traceback.print_exc()


if __name__ == "__main__":
    main()