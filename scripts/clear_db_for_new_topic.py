import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.db_helper import get_conn


def main():
    conn = get_conn()
    cur = conn.cursor()
    for table in ["sources", "extracted_info", "drafts", "review_specs", "search_runs"]:
        cur.execute("DELETE FROM {0}".format(table))
    conn.commit()
    conn.close()
    print("Cleared: sources, extracted_info, drafts, review_specs, search_runs")


if __name__ == "__main__":
    main()