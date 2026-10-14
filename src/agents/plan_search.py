import json
from src.llm import call_llm_json
from src.schemas import ReviewSpec

SYSTEM_PROMPT = """你是一个学术文献检索策略规划专家。
你的任务是根据综述规格（ReviewSpec），生成一组可执行的 PubMed 检索任务。
你必须严格只输出 JSON，不要输出任何解释。

检索策略原则：
- 每个检索任务对应综述的一个或几个章节，purpose 字段说明这个任务是为了回答什么问题。
- keywords 是 PubMed 的检索式，用 AND / OR 组合。核心实体用 [Title/Abstract] 限定。
- 对于药物名称，同时给出通用名、代号、商品名（如果有）。
- 对于疾病名称，同时给出 MeSH 主题词和自由词。
- 不要编造不存在的药物名称或试验编号。如果 ReviewSpec 中没有提供，就不要硬编。
- 每个任务给出 max_results（建议 10-30）和 time_range。"""

USER_PROMPT_TEMPLATE = """请根据以下综述规格，生成 PubMed 检索计划。

综述标题：{review_title}
核心实体：{core_entities}
章节结构：
{sections_text}
摘要要求：{abstract_requirements}
证据类型：{evidence_types}
时间范围：{time_range}

输出 JSON，格式如下：
{{
  "search_tasks": [
    {{
      "task_id": "简短英文标识，如 epi_global",
      "purpose": "这个检索是为了回答什么问题",
      "target_sections": [1, 2],
      "keywords": "PubMed 检索式，如 \\"major depressive disorder\\"[Title/Abstract] AND \\"global burden\\"[Title/Abstract]",
      "max_results": 20,
      "time_range": "2015-2026",
      "priority": "high | medium | low"
    }}
  ]
}}

要求：
- 至少生成 4 个检索任务，覆盖所有章节。
- 优先用 MeSH 词和 [Title/Abstract] 限定，提高召回准确性。
- keywords 必须是可直接发给 PubMed E-utilities 的检索式。

只输出 JSON。"""


def plan_search(spec: ReviewSpec) -> dict:
    """根据 ReviewSpec 生成 PubMed 检索计划。"""
    sections_text = "\n".join(
        f"  第{s.number}节：{s.title} —— {s.focus}"
        for s in spec.sections
    )
    prompt = USER_PROMPT_TEMPLATE.format(
        review_title=spec.review_title,
        core_entities=", ".join(spec.core_entities),
        sections_text=sections_text,
        abstract_requirements=", ".join(spec.abstract_requirements),
        evidence_types=", ".join(spec.evidence_types),
        time_range=spec.time_range or "不限",
    )
    plan = call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
    return plan


if __name__ == "__main__":
    import json
    from src.agents.parse_instruction import parse_instruction

    test_instruction = """帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史。
    摘要主要从抑郁症的全球趋势，抑郁症的发病原因，药物研发主要从哪些机制展开，JS1-1-01片的作用机制有哪些创新点。
    1引言介绍抑郁症和JS1-1-01片的基本情况。
    2JS1-1-01片的发现与临床前研究。
    3JS1-1-01片的研发历程。
    4JS1-1-01片的未来前景与挑战。"""

    spec = parse_instruction(test_instruction)
    plan = plan_search(spec)
    print(json.dumps(plan, ensure_ascii=False, indent=2))