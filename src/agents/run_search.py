from src.agents.plan_search import plan_search
from src.adapters.pubmed import search_and_fetch
from src.adapters.clinicaltrials import search_and_parse
from src.schemas import ReviewSpec


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


def run_search(spec: ReviewSpec) -> dict:
    """Execute search plan across PubMed and ClinicalTrials.gov."""
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

            all_results[task_id] = {
                "purpose": task.get("purpose", ""),
                "target_sections": task.get("target_sections", []),
                "database": database,
                "keywords": keywords,
                "count": len(records),
                "records": records,
            }
            print("[{0}][{1}] {2} records".format(database, task_id, len(records)))
        except Exception as e:
            all_results[task_id] = {"error": str(e), "keywords": keywords}
            print("[{0}][{1}] FAILED: {2}".format(database, task_id, e))

    return all_results


if __name__ == "__main__":
    from src.agents.parse_instruction import parse_instruction

    test_instruction = (
        "帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史。"
        "摘要主要从抑郁症的全球趋势，抑郁症的发病原因，药物研发主要从哪些机制展开，JS1-1-01片的作用机制有哪些创新点。"
        "1引言介绍抑郁症和JS1-1-01片的基本情况。"
        "2JS1-1-01片的发现与临床前研究。"
        "3JS1-1-01片的研发历程。"
        "4JS1-1-01片的未来前景与挑战。"
    )

    spec = parse_instruction(test_instruction)
    results = run_search(spec)

    print("\n=== Summary ===")
    for tid, r in results.items():
        print("  {0} [{1}]: {2}".format(tid, r.get("database", "?"), r.get("count", "FAILED")))