from src.agents.plan_search import plan_search
from src.adapters.pubmed import search_and_fetch
from src.adapters.clinicaltrials import search_and_parse
from src.schemas import ReviewSpec
from src.db.db_helper import save_many_sources, save_search_run


def _parse_time_range(time_range: str):
    if not time_range or "-" not in time_range:
        return None, None
    parts = time_range.split("-")
    if len(parts) != 2:
        return None, None
    start, end = parts[0].strip(), parts[1].strip()
    if not (start.isdigit() and end.isdigit()):
        return None, None
    return start + "/01/01", end + "/12/31"


def run_search(spec: ReviewSpec, spec_id: int = None) -> dict:
    """Execute search plan. Saves all sources to SQLite. Returns dict keyed by task_id."""
    plan = plan_search(spec)
    all_results = {}

    for task in plan.get("search_tasks", []):
        task_id = task["task_id"]
        keywords = task["keywords"]
        max_results = task.get("max_results", 20)
        database = task.get("database", "pubmed")

        try:
            if database == "clinicaltrials":
                records = search_and_parse(keywords, max_results)
            else:
                mindate, maxdate = _parse_time_range(task.get("time_range", ""))
                records = search_and_fetch(keywords, max_results, mindate, maxdate)

            saved_count = save_many_sources(records)
            if spec_id is not None:
                save_search_run(spec_id, task_id, database, keywords, len(records))

            all_results[task_id] = {
                "purpose": task.get("purpose", ""),
                "target_sections": task.get("target_sections", []),
                "database": database,
                "keywords": keywords,
                "count": len(records),
                "saved": saved_count,
                "records": records,
            }
            print("[{0}][{1}] {2} records, {3} saved".format(
                database, task_id, len(records), saved_count))
        except Exception as e:
            all_results[task_id] = {"error": str(e), "keywords": keywords}
            print("[{0}][{1}] FAILED: {2}".format(database, task_id, e))

    return all_results


if __name__ == "__main__":
    import sys
    import json
    from src.db.db_helper import init_db, get_conn
    from src.schemas import ReviewSpec

    init_db()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()

    if row is None:
        print("No ReviewSpec found. Run scripts\\run_new_review.py first.")
        sys.exit(1)

    spec = ReviewSpec(**json.loads(row["spec_json"]))
    print("Using spec: {0}".format(spec.review_title))
    results = run_search(spec)

    print("\n=== Summary ===")
    for tid, r in results.items():
        print("  {0} [{1}]: {2} records, {3} saved".format(
            tid, r.get("database", "?"), r.get("count", "FAILED"), r.get("saved", 0)))