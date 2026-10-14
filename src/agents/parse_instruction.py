from src.llm import call_llm_json
from src.schemas import ReviewSpec

SYSTEM_PROMPT = """你是一个学术综述撰写指令解析器。
你的任务是把用户的自然语言指令解析为结构化 JSON。
你必须严格只输出 JSON，不要输出任何解释性文字。
如果某个字段用户没有明确说明，根据综述写作常识合理推断，但不要编造具体数字或事实。"""

USER_PROMPT_TEMPLATE = """请解析以下综述撰写指令：

<指令>
{instruction}
</指令>

输出 JSON，字段如下：
{{
  "review_title": "综述标题",
  "review_type": "narrative_review | systematic_review | mini_review",
  "language": "中文 | 英文",
  "core_entities": ["核心实体1", "核心实体2"],
  "background_topics": ["背景主题1", "背景主题2"],
  "sections": [
    {{"number": 1, "title": "章节标题", "focus": "该节要写什么", "key_questions": ["问题1", "问题2"]}}
  ],
  "abstract_requirements": ["摘要需要覆盖的点1", "点2"],
  "evidence_types": ["clinical_trial", "preclinical", "patent", "company_announcement", "epidemiology", "review"],
  "time_range": "起止年份，如 2015-2026",
  "target_audience": "目标读者"
}}

只输出 JSON。"""


def parse_instruction(instruction: str) -> ReviewSpec:
    prompt = USER_PROMPT_TEMPLATE.format(instruction=instruction)
    raw = call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
    return ReviewSpec(**raw)


if __name__ == "__main__":
    from src.db.db_helper import init_db, save_spec

    init_db()
    test_instruction = """帮我撰写一个综述，临床三期抗抑郁药——JS1-1-01片的发展史。
    摘要主要从抑郁症的全球趋势，抑郁症的发病原因，药物研发主要从哪些机制展开，JS1-1-01片的作用机制有哪些创新点。
    1引言介绍抑郁症和JS1-1-01片的基本情况。
    2JS1-1-01片的发现与临床前研究。
    3JS1-1-01片的研发历程。
    4JS1-1-01片的未来前景与挑战。"""

    spec = parse_instruction(test_instruction)
    rid = save_spec(test_instruction, spec.model_dump())
    print(f"Saved spec id={rid}")
    print(spec.model_dump_json(indent=2))