import json
from src.llm import call_llm_json
from src.db.db_helper import get_source, get_conn
from src.schemas import ReviewSpec


SYSTEM_PROMPT = (
    "You are a biomedical research information extractor. "
    "Given a source record (journal article or clinical trial), extract structured information. "
    "Output ONLY JSON, no explanation. "
    "Do NOT invent information not present in the source. "
    "If a field is not available, use null or an empty list."
)

CLINICALTRIAL_PROMPT = """Extract structured information from this clinical trial registration.

{review_sections}

Trial data:
{trial_json}

Output JSON in this exact format:
{{
  "source_id": "{source_id}",
  "study_type": "interventional | observational | other",
  "phase": "Phase 1 | Phase 1b | Phase 2 | Phase 2/3 | Phase 3 | N/A",
  "sponsor": "sponsor name",
  "condition": "target disease",
  "interventions": ["list of interventions"],
  "enrollment": number or null,
  "enrollment_type": "ACTUAL | ESTIMATED | null",
  "primary_endpoint": "primary outcome measure",
  "start_date": "YYYY-MM or null",
  "completion_date": "YYYY-MM or null",
  "status": "trial status",
  "locations_summary": "countries and main sites",
  "key_facts": ["list of 3-5 key factual statements directly from the data"],
  "relevant_sections": ["section numbers from the list above, e.g. [3] or [3,4]"],
  "notes": "any caveats about data completeness"
}}

Output ONLY JSON."""

PUBMED_PROMPT = """Extract structured information from this PubMed article.

{review_sections}

Article:
Title: {title}
Journal: {journal}
Year: {year}
Authors: {authors}
Abstract: {abstract}

Output JSON in this exact format:
{{
  "source_id": "{source_id}",
  "study_type": "randomized_controlled_trial | cohort | case_control | cross_sectional | meta_analysis | systematic_review | narrative_review | preclinical | other",
  "population": "study population",
  "intervention_or_exposure": "drug, exposure, or main variable",
  "comparator": "control or comparison, or null",
  "primary_outcome": "primary outcome or research question",
  "key_findings": ["list of 2-5 key findings directly from the abstract"],
  "limitations": ["list of limitations if mentioned, else empty"],
  "relevant_sections": ["section numbers from the list above, e.g. [1] or [2,4]"],
  "evidence_level": "high | medium | low | unclear",
  "notes": "any caveats"
}}

Output ONLY JSON."""


def build_review_sections_block(spec: ReviewSpec) -> str:
    lines = ["The review has the following sections:"]
    for s in spec.sections:
        lines.append("- Section {0}: {1} -- {2}".format(s.number, s.title, s.focus))
    lines.append("")
    lines.append(
        "Assign each source to the review section(s) it DIRECTLY supports. "
        "A source can belong to MULTIPLE sections. Be strict: most sources support only 1-2 sections. "
        "Use ONLY section numbers from the list above. Do NOT invent section numbers."
    )
    core = ", ".join(spec.core_entities) if spec.core_entities else "(none specified)"
    lines.append("Core entities of this review: {0}".format(core))
    return "\n".join(lines)


def _load_latest_spec() -> ReviewSpec:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT spec_json FROM review_specs ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise ValueError("No ReviewSpec in DB")
    return ReviewSpec(**json.loads(row["spec_json"]))


def extract_clinicaltrial(source_id: str, spec: ReviewSpec) -> dict:
    source = get_source(source_id)
    if source is None:
        return {"error": "source not found", "source_id": source_id}

    trial_json = json.dumps(source, ensure_ascii=False, indent=2)
    prompt = CLINICALTRIAL_PROMPT.format(
        review_sections=build_review_sections_block(spec),
        trial_json=trial_json,
        source_id=source_id,
    )
    return call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)


def extract_pubmed(source_id: str, spec: ReviewSpec) -> dict:
    source = get_source(source_id)
    if source is None:
        return {"error": "source not found", "source_id": source_id}

    prompt = PUBMED_PROMPT.format(
        review_sections=build_review_sections_block(spec),
        title=source.get("title", ""),
        journal=source.get("journal", ""),
        year=source.get("year", ""),
        authors=", ".join(source.get("authors", [])[:5]),
        abstract=source.get("abstract", "") or "(no abstract available)",
        source_id=source_id,
    )
    return call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)


def save_extracted(source_id: str, extracted: dict) -> bool:
    try:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO extracted_info (source_id, extracted_json) VALUES (?, ?)",
            (source_id, json.dumps(extracted, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Failed to save extracted info {0}: {1}".format(source_id, e))
        return False


def extract_and_save(source_id: str, spec: ReviewSpec = None) -> dict:
    if spec is None:
        spec = _load_latest_spec()

    if source_id.startswith("ct_"):
        result = extract_clinicaltrial(source_id, spec)
    elif source_id.startswith("pubmed_"):
        result = extract_pubmed(source_id, spec)
    else:
        result = {"error": "unknown source type", "source_id": source_id}

    if "error" not in result:
        save_extracted(source_id, result)
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        sid = sys.argv[1]
        result = extract_and_save(sid)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Usage: python -m src.agents.extract_info <source_id>")