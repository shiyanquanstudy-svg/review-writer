import json
from src.llm import call_llm_json
from src.schemas import ReviewSpec

SYSTEM_PROMPT = (
    "You are an expert in planning academic literature search strategies. "
    "Given a review specification, generate search tasks for BOTH PubMed and ClinicalTrials.gov. "
    "Output ONLY JSON, no explanation.\n\n"
    "For PubMed tasks:\n"
    "- keywords must be a valid PubMed query using AND/OR and [Title/Abstract] or MeSH terms.\n"
    "- For drug names, include code names and generic names if applicable.\n"
    "- For disease names, include both MeSH terms and free-text terms.\n\n"
    "For ClinicalTrials.gov tasks:\n"
    "- keywords should be simple search terms: drug code name, sponsor name, or disease plus intervention.\n"
    "- Do NOT use PubMed syntax in ClinicalTrials keywords.\n"
    "- Use database='clinicaltrials' to mark them.\n\n"
    "Each task should have max_results (10-30) and a time_range.\n"
    "Do NOT invent drug names or trial IDs not present in the spec."
)

USER_PROMPT_TEMPLATE = """Generate a search plan based on the following review specification.

Review title: {review_title}
Core entities: {core_entities}
Sections:
{sections_text}
Abstract requirements: {abstract_requirements}
Evidence types: {evidence_types}
Time range: {time_range}

Output JSON in this exact format:
{{
  "search_tasks": [
    {{
      "task_id": "short English id",
      "purpose": "what question this search answers",
      "target_sections": [1, 2],
      "database": "pubmed",
      "keywords": "PubMed query string",
      "max_results": 20,
      "time_range": "2015-2026",
      "priority": "high"
    }},
    {{
      "task_id": "short English id",
      "purpose": "what question this search answers",
      "target_sections": [3],
      "database": "clinicaltrials",
      "keywords": "simple search term, e.g. JS1-1-01",
      "max_results": 20,
      "time_range": "any",
      "priority": "high"
    }}
  ]
}}

Requirements:
- Generate at least 4 tasks total, covering all sections.
- Use database='clinicaltrials' for tasks targeting drug codes, sponsor names, or registered trials.
- Use database='pubmed' for tasks targeting mechanisms, epidemiology, and review literature.
- For every drug code in core_entities, generate at least one clinicaltrials task.
- keywords must be directly usable with the respective API.

Output ONLY JSON."""


def plan_search(spec: ReviewSpec) -> dict:
    sections_text = "\n".join(
        "  Section {0}: {1} -- {2}".format(s.number, s.title, s.focus)
        for s in spec.sections
    )
    prompt = USER_PROMPT_TEMPLATE.format(
        review_title=spec.review_title,
        core_entities=", ".join(spec.core_entities),
        sections_text=sections_text,
        abstract_requirements=", ".join(spec.abstract_requirements),
        evidence_types=", ".join(spec.evidence_types),
        time_range=spec.time_range or "any",
    )
    return call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.1)


if __name__ == "__main__":
    from src.agents.parse_instruction import parse_instruction

    test_instruction = (
        "Help me write a review on the development history of JS1-1-01, "
        "a phase 3 antidepressant drug. The abstract should cover global depression trends, "
        "causes of depression, major antidepressant mechanisms, and JS1-1-01's innovation. "
        "Section 1: Introduction to depression and JS1-1-01. "
        "Section 2: Discovery and preclinical studies of JS1-1-01. "
        "Section 3: Clinical development history of JS1-1-01. "
        "Section 4: Future prospects and challenges of JS1-1-01."
    )

    spec = parse_instruction(test_instruction)
    plan = plan_search(spec)
    print(json.dumps(plan, ensure_ascii=False, indent=2))