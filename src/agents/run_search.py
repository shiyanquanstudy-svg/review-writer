import json
from src.agents.plan_search import plan_search
from src.adapters.pubmed import search_and_fetch
from src.schemas import ReviewSpec


def run_search(spec: ReviewSpec) -> dict:
    """执行检索规划 + PubMed 检索，返回按任务分组的结果。"""
    plan = plan_search(spec)
    all_results = {}

    for task in plan.get("search_tasks", []):
        task_id = task["task_id"]
        keywords = task["keywords"]
        max_results = task.get("max_results", 20)

        time_range = task.get("time_range", "")
        mindate = maxdate = None
        if "-" in time_range:
            parts = time_range.split("-")
            if len(parts) == 2 and parts[0].strip().isdigit():
                mindate = f"{parts[0].strip()}/01/01"
                maxdate = f"{parts[1].strip()}/12/31"

        try:
            records = search_and_fetch(keywords, max_results, mindate, maxdate)
            all_results[task_id] = {
                "purpose": task["purpose"],
                "target_sections": task.get("target_sections", []),
                "keywords": keywords,
                "count": len(records),
                "records": records,
            }
            print(f"[{task_id}] {len(records)} 条结果 —— {task['purpose']}")
        except Exception as e:
            all_results[task_id] = {"error": str(e), "keywords": keywords}
            print(f"[{task_id}] 失败: {e}")

    return all_results


if __name__ == "__main__":
    from src.agents.parse_instruction import parse_instruction

    test_instruction = """帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史。
    摘要主要从抑郁症的全球趋势，抑郁症的发病原因，药物研发主要从哪些机制展开，JS1-1-01片的作用机制有哪些创新点。
    1引言介绍抑郁症和JS1-1-01片的基本情况。
    2JS1-1-01片的发现与临床前研究。
    3JS1-1-01片的研发历程。
    4JS1-1-01片的未来前景与挑战。"""

    spec = parse_instruction(test_instruction)
    results = run_search(spec)

    total = sum(r.get("count", 0) for r in results.values())
    print(f"\n总计检索到 {total} 条文献")
    for tid, r in results.items():
        print(f"  {tid}: {r.get('count', '失败')} 条")