import json
from src.llm import call_llm_json
from src.db.db_helper import get_conn
from src.schemas import ReviewSpec
from src.agents.language_utils import outline_language_instruction


SYSTEM_PROMPT = (
    "You are an academic review outline architect. "
    "Given a review specification and a set of extracted sources, "
    "produce a detailed outline for ONE section. "
    "Output ONLY JSON, no explanation. "
    "Do NOT invent sources, facts, or section numbers. "
    "Only use source_ids from the provided list."
)

SECTION_OUTLINE_PROMPT = """Design the detailed outline for one section of a review.

Review title: {review_title}
Review type: {review_type}
Target audience: {target_audience}

Full review structure (for context):
{all_sections}

Now focus on Section {section_number}: {section_title}
Section focus: {section_focus}
Key questions to answer:
{key_questions}

Available sources for this section (with extracted findings):
{sources_block}

Generate a detailed outline for Section {section_number} as JSON:

{{
  "section_number": {section_number},
  "title": "{section_title}",
  "thesis": "one sentence stating the central argument of this section",
  "key_points": [
    "point 1 (each point should be supportable by at least one source below)",
    "point 2"
  ],
  "supporting_sources": ["source_id 1", "source_id 2"],
  "estimated_words": 600,
  "notes": "any caveats about evidence availability for this section"
}}

Rules:
- key_points should be 3-6 concrete, non-overlapping points.
- supporting_sources must be a subset of the provided source_ids. Do NOT invent IDs.
- If a section has very few or zero sources, note this in `notes` and reduce estimated_words.
- estimated_words: Section 1 = 500-800, Section 2 = 600-900, Section 3 = 700-1000, Section 4 = 400-700.
- key_points must be answerable using only the provided sources.

Language requirement:
{language_instruction}

Output ONLY JSON."""


def _normalize_sections(raw_sections) -> list:
    if raw_sections is None:
        return []
    if isinstance(raw_sections, (str, int)):
        raw_sections = [raw_sections]
    result = []
    for s in raw_sections:
        try:
            result.append(int(s))
        except (ValueError, TypeError):
            continue
    return result


def load_latest_spec() -> tuple:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise ValueError("No ReviewSpec found in DB")
    return ReviewSpec(**json.loads(row["spec_json"])), row["id"]


def load_extracted_sources() -> dict:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT source_id, extracted_json FROM extracted_info")
    rows = cur.fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        source_id = row["source_id"]
        try:
            extracted = json.loads(row["extracted_json"])
        except Exception:
            continue
        sections = _normalize_sections(extracted.get("relevant_sections", []))
        for sec in sections:
            grouped.setdefault(sec, []).append({
                "source_id": source_id,
                "extracted": extracted,
            })
    return grouped


def _format_sources_block(sources: list) -> str:
    if not sources:
        return "(no sources available for this section)"

    lines = []
    for item in sources:
        sid = item["source_id"]
        ex = item["extracted"]
        study_type = ex.get("study_type", "unknown")

        facts = ex.get("key_findings") or ex.get("key_facts") or []
        facts_text = " | ".join(facts[:3]) if facts else "(no key findings)"

        lines.append("- {0} [{1}]: {2}".format(sid, study_type, facts_text))
    return "\n".join(lines)


def generate_section_outline(spec: ReviewSpec, section, sources: list) -> dict:
    all_sections = "\n".join(
        "  Section {0}: {1} -- {2}".format(s.number, s.title, s.focus)
        for s in spec.sections
    )
    key_questions = "\n".join("  - " + q for q in section.key_questions) or "  (none specified)"

    prompt = SECTION_OUTLINE_PROMPT.format(
        review_title=spec.review_title,
        review_type=spec.review_type,
        target_audience=spec.target_audience,
        all_sections=all_sections,
        section_number=section.number,
        section_title=section.title,
        section_focus=section.focus,
        key_questions=key_questions,
        sources_block=_format_sources_block(sources),
        language_instruction=outline_language_instruction(spec.language),
    )
    return call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.2)


def generate_outline(spec: ReviewSpec = None) -> dict:
    if spec is None:
        spec, spec_id = load_latest_spec()
    else:
        spec_id = None

    grouped = load_extracted_sources()

    outline_sections = []
    for section in spec.sections:
        sources = grouped.get(section.number, [])
        print("[Section {0}] {1} source(s) available".format(section.number, len(sources)))
        section_outline = generate_section_outline(spec, section, sources)
        outline_sections.append(section_outline)

    return {
        "review_title": spec.review_title,
        "review_type": spec.review_type,
        "language": spec.language,
        "sections": outline_sections,
    }


if __name__ == "__main__":
    outline = generate_outline()
    print(json.dumps(outline, ensure_ascii=False, indent=2))