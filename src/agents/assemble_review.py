import json
import re
from datetime import datetime
from src.llm import call_llm
from src.db.db_helper import get_conn, get_source
from src.schemas import ReviewSpec


ABSTRACT_SYSTEM = (
    "You are an academic review abstract writer. "
    "Given a review specification and the four section drafts, write a single structured abstract. "
    "Output plain Chinese prose, no heading, no markdown. "
    "Do NOT fabricate data. Only use facts that appear in the provided drafts."
)

ABSTRACT_PROMPT = """请根据以下综述信息，撰写一段结构化摘要（250-350字）。

综述标题：{review_title}
摘要要求覆盖：{abstract_requirements}

第1节（引言）正文：
{section1}

第2节（发现与临床前研究）正文：
{section2}

第3节（研发历程）正文：
{section3}

第4节（未来前景与挑战）正文：
{section4}

要求：
1. 摘要需覆盖以下要点：抑郁症的全球趋势与发病机制概况、抗抑郁药研发的主要机制方向、JS1-1-01片的研发现状与已注册临床证据、JS1-1-01片面临的主要挑战与证据缺口。
2. 不得写入正文中未出现的具体数字或事实。
3. 语言学术、客观、简洁。
4. 只输出摘要正文，不加"摘要："前缀，不加 markdown。

摘要正文："""


def _load_latest_spec():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise ValueError("No ReviewSpec found")
    return ReviewSpec(**json.loads(row["spec_json"])), row["id"]


def _load_latest_drafts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT section_number, content
        FROM drafts d1
        WHERE id = (
            SELECT MAX(id) FROM drafts d2
            WHERE d2.section_number = d1.section_number
        )
        ORDER BY section_number
    """)
    rows = cur.fetchall()
    conn.close()
    return {row["section_number"]: row["content"] for row in rows}


def _extract_all_cited_source_ids(text: str) -> list:
    return re.findall(r"\[(pubmed_\d+|ct_[A-Z0-9]+)\]", text)


def _format_reference(sid: str, source: dict, index: int) -> str:
    authors = source.get("authors") or []
    if authors:
        if len(authors) > 6:
            author_str = ", ".join(authors[:6]) + ", et al"
        else:
            author_str = ", ".join(authors)
    else:
        author_str = source.get("sponsor") or "Unknown"

    year = source.get("year") or ""
    if not year and source.get("start_date"):
        year = str(source["start_date"])[:4]

    if sid.startswith("ct_"):
        nct = source.get("nct_id") or sid.replace("ct_", "")
        title = source.get("title") or source.get("official_title") or ""
        url = source.get("url") or ""
        return "{0}. {1}. ClinicalTrials.gov identifier: {2}. {3}. Available from: {4}".format(
            index, author_str, nct, title, url
        )
    else:
        title = source.get("title") or ""
        journal = source.get("journal") or ""
        doi = source.get("doi") or ""
        url = source.get("url") or ""
        parts = ["{0}. {1}. {2}.".format(index, author_str, title)]
        if journal:
            parts.append(" {0}.".format(journal))
        if year:
            parts.append(" {0}.".format(year))
        if doi:
            parts.append(" doi:{0}.".format(doi))
        if url:
            parts.append(" Available from: {0}".format(url))
        return "".join(parts)


def generate_abstract(spec, drafts):
    prompt = ABSTRACT_PROMPT.format(
        review_title=spec.review_title,
        abstract_requirements=", ".join(spec.abstract_requirements),
        section1=drafts.get(1, "")[:2000],
        section2=drafts.get(2, "")[:2000],
        section3=drafts.get(3, "")[:2000],
        section4=drafts.get(4, "")[:2000],
    )
    return call_llm(prompt, system=ABSTRACT_SYSTEM, temperature=0.3).strip()


def assemble(output_path="data/review_output.md"):
    spec, spec_id = _load_latest_spec()
    drafts = _load_latest_drafts()

    print("Sections found: {0}".format(sorted(drafts.keys())))

    print("Generating abstract...")
    abstract = generate_abstract(spec, drafts)

    # Collect all cited source_ids across abstract + drafts
    all_text = abstract + "\n" + "\n".join(drafts.values())
    cited_ids = _extract_all_cited_source_ids(all_text)
    # Deduplicate while preserving order
    seen = set()
    ordered_ids = []
    for sid in cited_ids:
        if sid not in seen:
            seen.add(sid)
            ordered_ids.append(sid)

    print("Cited sources: {0}".format(len(ordered_ids)))

    # Build reference list
    references = []
    for i, sid in enumerate(ordered_ids, 1):
        src = get_source(sid)
        if src is None:
            print("  WARNING: source not found: {0}".format(sid))
            continue
        references.append(_format_reference(sid, src, i))

    # Build markdown
    lines = []
    lines.append("# {0}".format(spec.review_title))
    lines.append("")
    lines.append("*生成时间：{0}*".format(datetime.now().strftime("%Y-%m-%d")))
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append(abstract)
    lines.append("")

    # Keywords
    keywords = list(spec.core_entities) + list(spec.background_topics)[:3]
    lines.append("**关键词：** {0}".format("；".join(keywords)))
    lines.append("")

    # Sections
    for section in spec.sections:
        content = drafts.get(section.number, "")
        if not content:
            continue
        lines.append("## {0}. {1}".format(section.number, section.title))
        lines.append("")
        lines.append(content)
        lines.append("")

    # References
    lines.append("## 参考文献")
    lines.append("")
    for ref in references:
        lines.append("{0}".format(ref))
        lines.append("")

    markdown = "\n".join(lines)

    from pathlib import Path
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")

    print("Written to {0}".format(out.resolve()))
    print("Total length: {0} chars".format(len(markdown)))
    return markdown


if __name__ == "__main__":
    assemble()