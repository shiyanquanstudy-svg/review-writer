import json
from src.llm import call_llm
from src.db.db_helper import get_conn, get_source
from src.schemas import ReviewSpec
from src.agents.rank_sources import rank_all


WRITER_SYSTEM_PROMPT = (
    "You are a senior academic review writer. "
    "You write ONE section of a review at a time. "
    "You must follow strict evidence rules:\n"
    "- Do NOT fabricate facts, dates, numbers, or citations.\n"
    "- Every factual statement about the review's core entity must cite a Category A source using [source_id].\n"
    "- Statements about the general class may cite Category B sources with [source_id].\n"
    "- Only use source_ids from the provided lists. Do NOT invent source_ids.\n"
    "- If a key point has no Category A evidence, use Category B but explicitly frame it as class-level data, and note that core-entity-specific evidence is pending.\n"
    "- Do NOT write specific numbers, dates, or findings that are not present in the provided sources.\n"
    "- Write in formal academic Chinese.\n"
    "- Output plain prose paragraphs. Do NOT include section headings or markdown."
)

SECTION_WRITER_PROMPT = """请为以下综述撰写第 {section_number} 节。

综述标题：{review_title}
综述类型：{review_type}
目标读者：{target_audience}
综述核心实体：{core_entities}

第 {section_number} 节：{section_title}
本节中心论点：{thesis}

需覆盖的要点（按顺序）：
{key_points_block}

证据分两类：

【A 类：核心实体直接证据】（关于 {core_entities} 的陈述只能引用这些）
{sources_direct_block}

【B 类：相关领域上下文】（同类药物、相关机制、领域背景，仅用于讨论"类"层面的内容）
{sources_context_block}

严格规则：
1. 任何关于 {core_entities} 具体机制、发现过程、试验数据、时间线的陈述，必须引用 A 类源，用 [source_id] 标注。
2. B 类源只能用于讨论"该类"或"领域趋势"等类层面内容，不得把其他对象的数据、结论安到核心实体头上。
3. 若某要点没有 A 类证据，可以用 B 类支撑，但必须在文中明确写出"该类数据显示……{core_entities} 的同类数据尚未公开发表"之类的表述，并如实说明证据缺口。
4. 每段末尾附一个引用汇总，格式：[Sources: pubmed_xxx, pubmed_yyy]。
5. 目标长度约 {estimated_words} 字。
6. 只输出正文，不含标题、不含"第 X 节"字样、不含 markdown 标题。
7. 【前后一致性】在讨论"证据缺口"时，必须区分"机制/临床前证据缺失"与"临床注册信息已有"等不同证据类型，不得笼统否定已有证据的存在。
8. 【数字必引】任何包含具体数值（IC50、nM、百分比、入组例数、年数、剂量）或具体实验结果（如"在悬尾实验中减少不动时间"）的句子，句末必须紧跟其来源 [source_id]。若来源不在 A/B 类清单中，则改用定性描述，不得写出具体数值。禁止出现无 [source_id] 标注的具体数字。
9. 【禁用内部知识】你只能使用上面 A/B 类源清单中明确列出的数据。即使你"记得"某篇论文的具体数值或结论，如果它不在清单中，也绝对不得写出。
10. 【禁止对核心实体做路径推断】不得写"{core_entities} 的发现遵循了……路径"这类编造来源的句子。若确需说明，必须写成"该类药物的研发通常遵循……；{core_entities} 的具体路径尚无公开证据"。
11. 【一源一句】当一句包含多个独立事实时，每个事实应紧跟其自身来源，避免在句末堆积引用。

现在请撰写第 {section_number} 节正文。"""


def _is_direct_evidence(source_id: str, source_data: dict, spec: ReviewSpec) -> bool:
    """A source is 'direct evidence' if:
       - it is a registered clinical trial, OR
       - its title mentions a CONCRETE core entity (drug code / compound name), OR
       - the review's core entities are domain-level topics, in which case
         any source assigned to this section counts as direct evidence."""
    if source_id.startswith("ct_"):
        return True

    title = (source_data.get("title") or "").lower()

    def _looks_specific(entity: str) -> bool:
        e = entity.strip()
        if not e:
            return False
        has_digit = any(ch.isdigit() for ch in e)
        has_hyphen = "-" in e
        if has_digit and (has_hyphen or len(e) <= 12):
            return True
        return False

    specific_entities = [e for e in spec.core_entities if _looks_specific(e)]

    if specific_entities:
        for entity in specific_entities:
            if entity.lower() in title:
                return True
        return False
    else:
        # Domain review: every assigned source is direct evidence
        return True


def _format_source_line(source_id: str, extracted: dict) -> str:
    study_type = extracted.get("study_type", "unknown")
    facts = extracted.get("key_findings") or extracted.get("key_facts") or []
    facts_text = " | ".join(facts[:3]) if facts else "(no key facts)"
    return "- [{0}] {1}: {2}".format(source_id, study_type, facts_text)


def _build_blocks(ranked_sources: list, spec: ReviewSpec) -> tuple:
    direct_lines = []
    context_lines = []

    for item in ranked_sources:
        sid = item["source_id"]
        src = get_source(sid)
        if src is None:
            continue

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT extracted_json FROM extracted_info WHERE source_id = ?", (sid,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            continue
        extracted = json.loads(row["extracted_json"])

        line = _format_source_line(sid, extracted)
        if _is_direct_evidence(sid, src, spec):
            direct_lines.append(line)
        else:
            context_lines.append(line)

    if not direct_lines:
        direct_lines.append("(无直接证据，仅可引用 B 类源做类层面推断)")
    if not context_lines:
        context_lines.append("(无类上下文源)")

    return "\n".join(direct_lines), "\n".join(context_lines)


def write_section(spec: ReviewSpec, section_outline: dict, ranked_sources: list) -> str:
    direct_block, context_block = _build_blocks(ranked_sources, spec)

    key_points = section_outline.get("key_points", [])
    key_points_block = "\n".join("{0}. {1}".format(i + 1, kp) for i, kp in enumerate(key_points))

    core_entities_str = "、".join(spec.core_entities) if spec.core_entities else "核心实体"

    prompt = SECTION_WRITER_PROMPT.format(
        section_number=section_outline["section_number"],
        review_title=spec.review_title,
        review_type=spec.review_type,
        target_audience=spec.target_audience,
        core_entities=core_entities_str,
        section_title=section_outline["title"],
        thesis=section_outline.get("thesis", ""),
        key_points_block=key_points_block,
        sources_direct_block=direct_block,
        sources_context_block=context_block,
        estimated_words=section_outline.get("estimated_words", 600),
    )
    return call_llm(prompt, system=WRITER_SYSTEM_PROMPT, temperature=0.4)


def save_draft(spec_id: int, section_number: int, content: str, citations: list):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO drafts (spec_id, section_number, content, citations_json)
        VALUES (?, ?, ?, ?)""",
        (spec_id, section_number, content, json.dumps(citations, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def write_all(top_n: int = 12, only_section: int = None) -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    spec = ReviewSpec(**json.loads(row["spec_json"]))
    spec_id = row["id"]

    rank_result = rank_all(top_n=top_n, spec=spec)
    rank_by_section = {s["section_number"]: s for s in rank_result["sections"]}

    from src.agents.generate_outline import generate_outline
    outline = generate_outline(spec)
    outline_by_section = {s["section_number"]: s for s in outline["sections"]}

    results = {}
    for section in spec.sections:
        sec_num = section.number
        if only_section is not None and sec_num != only_section:
            continue

        sec_outline = outline_by_section.get(sec_num, {})
        sec_rank = rank_by_section.get(sec_num, {})
        ranked_sources = sec_rank.get("ranked_sources", [])

        print("[Section {0}] writing ({1} sources)...".format(sec_num, len(ranked_sources)))
        try:
            content = write_section(spec, sec_outline, ranked_sources)
            citations = [s["source_id"] for s in ranked_sources]
            save_draft(spec_id, sec_num, content, citations)
            results[sec_num] = {
                "title": section.title,
                "content": content,
                "sources_used": citations,
                "char_count": len(content),
            }
            print("  {0} chars".format(len(content)))
        except Exception as e:
            print("  FAILED: {0}".format(e))
            results[sec_num] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import sys
    only = None
    if len(sys.argv) > 1:
        only = int(sys.argv[1])

    result = write_all(only_section=only)

    for k, v in sorted(result.items()):
        print("\n" + "=" * 60)
        print("Section {0}: {1}".format(k, v.get("title", "")))
        print("=" * 60)
        print(v.get("content", v.get("error", "")))