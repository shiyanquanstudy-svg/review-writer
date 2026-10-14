import json
from src.llm import call_llm_json
from src.db.db_helper import get_conn
from src.schemas import ReviewSpec


SYSTEM_PROMPT = (
    "You are a strict relevance ranker for academic review writing. "
    "Given a section focus and a batch of candidate sources, "
    "score each source on how directly it supports that section. "
    "Output ONLY JSON. Do NOT invent source_ids."
)

RANK_PROMPT = """You are ranking sources for ONE section of an academic review.

Review title: {review_title}
Core entities of the review: {core_entities}

Target section: Section {section_number} - {section_title}
Section focus: {section_focus}
Key questions of this section:
{key_questions}

Candidate sources (batch {batch_index}):
{sources_block}

For each source, assign a relevance score from 0 to 10:
- 10 = directly about this review's core entity OR provides the exact evidence this section needs
- 7-9 = closely related mechanism/class/context that this section must cite
- 4-6 = useful background but not central
- 1-3 = tangential, only loosely related
- 0 = unrelated (e.g. different drug, different disease, different topic)

Flag a source as entity mismatch ONLY if:
- The source is about a compound that could be CONFUSED with the review's core entity (same class AND same indication AND similar naming), OR
- The source was mistakenly retrieved as if it were about the core entity itself.

Do NOT flag a source merely because it studies a DIFFERENT drug/compound in the same class. Studies of other class members are VALID background sources and must NOT be flagged.

Output JSON in this exact format:
{{
  "scores": [
    {{"source_id": "pubmed_xxx", "score": 8, "reason": "one sentence"}}
  ],
  "flagged_entity_mismatch": ["source_id 1", "source_id 2"]
}}

Output ONLY JSON."""

# Populated per-review if needed. Empty for generic use.
HARDCODED_DENYLIST = set()


def _normalize_sections(raw_sections):
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


def load_grouped_sources():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.source_id, e.extracted_json, s.title
        FROM extracted_info e
        LEFT JOIN sources s ON e.source_id = s.source_id
    """)
    rows = cur.fetchall()
    conn.close()

    grouped = {}
    for row in rows:
        try:
            extracted = json.loads(row["extracted_json"])
        except Exception:
            continue
        sections = _normalize_sections(extracted.get("relevant_sections", []))
        for sec in sections:
            grouped.setdefault(sec, []).append({
                "source_id": row["source_id"],
                "extracted": extracted,
                "title": row["title"] or "",
            })
    return grouped


def _format_batch(sources):
    lines = []
    for item in sources:
        sid = item["source_id"]
        ex = item["extracted"]
        st = ex.get("study_type", "unknown")
        facts = (ex.get("key_findings") or ex.get("key_facts") or [])[:2]
        facts_text = " | ".join(facts) if facts else "(no facts)"
        lines.append("- {0} [{1}] {2}".format(sid, st, item["title"][:80]))
        lines.append("    {0}".format(facts_text[:180]))
    return "\n".join(lines)


def rank_section(spec, section, sources, batch_size=15):
    all_scores = {}
    all_flags = set()

    for i in range(0, len(sources), batch_size):
        batch = sources[i:i + batch_size]
        batch_index = i // batch_size + 1
        prompt = RANK_PROMPT.format(
            review_title=spec.review_title,
            core_entities=", ".join(spec.core_entities),
            section_number=section.number,
            section_title=section.title,
            section_focus=section.focus,
            key_questions="\n".join("  - " + q for q in section.key_questions),
            batch_index=batch_index,
            sources_block=_format_batch(batch),
        )
        result = call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)
        for item in result.get("scores", []):
            sid = item.get("source_id")
            score = item.get("score", 0)
            reason = item.get("reason", "")
            if sid:
                all_scores[sid] = {"score": score, "reason": reason}
        for sid in result.get("flagged_entity_mismatch", []) or []:
            all_flags.add(sid)

    return all_scores, all_flags


def rank_all(top_n=12, spec: ReviewSpec = None):
    if spec is None:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        spec = ReviewSpec(**json.loads(row["spec_json"]))

    grouped = load_grouped_sources()
    output = {"review_title": spec.review_title, "sections": []}

    for section in spec.sections:
        sources = grouped.get(section.number, [])
        print("[Section {0}] ranking {1} sources...".format(section.number, len(sources)))
        scores, flags = rank_section(spec, section, sources)

        filtered_scores = {
            sid: v for sid, v in scores.items()
            if sid not in flags and sid not in HARDCODED_DENYLIST
        }

        ranked = sorted(
            filtered_scores.items(),
            key=lambda kv: (-kv[1]["score"], kv[0]),
        )[:top_n]

        top_sources = [
            {"source_id": sid, "score": v["score"], "reason": v["reason"]}
            for sid, v in ranked
        ]

        output["sections"].append({
            "section_number": section.number,
            "title": section.title,
            "ranked_sources": top_sources,
            "entity_mismatch_flags": sorted(flags),
            "total_candidates": len(sources),
        })

    return output


if __name__ == "__main__":
    import sys
    top_n = 12
    if len(sys.argv) > 1:
        top_n = int(sys.argv[1])
    result = rank_all(top_n=top_n)
    print(json.dumps(result, ensure_ascii=False, indent=2))