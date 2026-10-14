import re
import json
from src.llm import call_llm_json
from src.db.db_helper import get_conn, get_source


SYSTEM_PROMPT = (
    "You are a citation verification specialist. "
    "Given a sentence from a review draft and the source it cites, "
    "judge whether the source actually supports the sentence. "
    "Output ONLY JSON. Be strict and literal."
)

VERIFY_PROMPT = """Verify this citation.

Sentence from draft:
"{sentence}"

Cited source ID: {source_id}

Source metadata:
- Title: {title}
- Year: {year}
- Abstract/facts: {abstract_or_facts}

Your task:
1. Does the source DIRECTLY support the claim in the sentence?
2. Pay special attention to whether the entity (drug, disease, population) matches.

Output JSON:
{{
  "verdict": "supported | partially_supported | not_supported | cannot_determine",
  "reason": "one sentence",
  "entity_mismatch": true | false
}}

Output ONLY JSON."""

# Sentence MUST contain one of these to count as "needs citation"
STRONG_FACT_PATTERNS = [
    r"\d+\.\d+\s*(nM|μM|mM|mg|kg|%|例|名|岁)",   # specific measurements
    r"IC50|EC50|Ki|AUC|Cmax",
    r"显示|表明|报告|发现|证实|揭示",
    r"入组|纳入|共\s*\d+|n\s*=\s*\d+",
    r"达到|高达|约为|约\s*\d",
    r"在\s*[\u4e00-\u9fa5A-Za-z]+\s*(?:实验|模型|研究)中",
    r"(?:showed|reported|found|demonstrated|enrolled|approximately|significant)",
]


def _split_sentences(text: str) -> list:
    """Split on Chinese/English sentence endings, but NOT on decimal points."""
    # First protect decimal points
    text = re.sub(r"(\d)\.(\d)", r"\1<DOT>\2", text)
    # Split on sentence endings
    parts = re.split(r"(?<=[。！？!?])|(?<=\.)(?=\s|$)", text)
    # Restore decimal points
    parts = [p.replace("<DOT>", ".").strip() for p in parts]
    return [p for p in parts if p]


def _extract_citations(sentence: str) -> list:
    return re.findall(r"\[(pubmed_\d+|ct_[A-Z0-9]+)\]", sentence)


def _needs_citation(sentence: str) -> bool:
    """A sentence needs a citation if it makes a factual claim that must be sourced.
    Meta-statements (disclaimers, analytical conclusions, methodological framing)
    do NOT need citations."""

    # Meta-statement patterns — no citation needed
    META_PATTERNS = [
        r"尚无公开.{0,10}证据",
        r"尚未.{0,10}(发表|披露|公开)",
        r"系基于.{0,20}推断",
        r"构成.{0,10}方法学背景",
        r"上述内容.{0,10}属于",
        r"这些(数据|结果).{0,8}(表明|说明)",
        r"需要(指出|说明)的是",
        r"本节.{0,10}(无法|未)",
        r"有待.{0,20}(证实|验证|明确)",
        r"总体而言|综上|由此可见|因此|这表明",
        r"上述.{0,15}(提示|说明|表明)",
        r"这一.{0,10}(证据缺口|结论|观察)",
        r"就.{0,15}而言",
        r"从.{0,15}(角度|层面|视角).{0,10}(看|而言)",
    ]
    for pat in META_PATTERNS:
        if re.search(pat, sentence):
            return False

    # A sentence with a [source_id] citation is almost always factual
    if re.search(r"\[(pubmed_\d+|ct_[A-Z0-9]+)\]", sentence):
        return True

    # Strong factual patterns — these DO need citations even without tags
    STRONG_PATTERNS = [
        r"\d+\.\d+\s*(nM|μM|mM|mg|kg|%)",
        r"IC50|EC50|Ki|AUC|Cmax",
        r"入组|纳入|共\s*\d+|n\s*=\s*\d+",
        r"约为|高达|达到",
        r"(?:显示|表明|报告|发现|证实|揭示).{0,30}\d",
        r"在\s*[\u4e00-\u9fa5A-Za-z0-9]+\s*(?:实验|模型|研究)中",
        r"(?:showed|reported|found|demonstrated|enrolled).{0,30}\d",
    ]
    for pat in STRONG_PATTERNS:
        if re.search(pat, sentence):
            return True
    return False


def _build_source_text(source_id: str):
    src = get_source(source_id)
    if src is None:
        return None, None, None

    title = src.get("title") or ""
    year = src.get("year") or src.get("start_date") or ""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT extracted_json FROM extracted_info WHERE source_id = ?", (source_id,))
    row = cur.fetchone()
    conn.close()

    if row:
        ex = json.loads(row["extracted_json"])
        facts = ex.get("key_findings") or ex.get("key_facts") or []
        facts_text = " | ".join(facts[:5])
    else:
        facts_text = src.get("abstract") or ""

    return title, year, facts_text


def verify_draft(text: str, section_number: int = None) -> dict:
    sentences = _split_sentences(text)

    results = []
    supported = 0
    unsupported = 0
    partially = 0
    uncited = 0
    commentary = 0

    for sent in sentences:
        needs_cite = _needs_citation(sent)
        citations = _extract_citations(sent)

        if not needs_cite:
            commentary += 1
            continue

        if not citations:
            uncited += 1
            results.append({
                "sentence": sent[:140],
                "citations": [],
                "verdict": "uncited",
            })
            continue

        for sid in citations:
            title, year, facts = _build_source_text(sid)
            if title is None:
                results.append({
                    "sentence": sent[:140],
                    "citations": [sid],
                    "verdict": "source_not_found",
                })
                continue

            prompt = VERIFY_PROMPT.format(
                sentence=sent[:300],
                source_id=sid,
                title=title[:150],
                year=year,
                abstract_or_facts=(facts or "")[:600],
            )
            try:
                result = call_llm_json(prompt, system=SYSTEM_PROMPT, temperature=0.0)
                verdict = result.get("verdict", "cannot_determine")
                if verdict == "supported":
                    supported += 1
                elif verdict == "not_supported":
                    unsupported += 1
                elif verdict == "partially_supported":
                    partially += 1

                results.append({
                    "sentence": sent[:140],
                    "citations": [sid],
                    "verdict": verdict,
                    "reason": result.get("reason", ""),
                    "entity_mismatch": result.get("entity_mismatch", False),
                })
            except Exception as e:
                results.append({
                    "sentence": sent[:140],
                    "citations": [sid],
                    "verdict": "error",
                    "reason": str(e),
                })

    total_needs_citation = supported + unsupported + partially + uncited
    strict_rate = round(supported / total_needs_citation, 3) if total_needs_citation else 0.0

    return {
        "section_number": section_number,
        "sentences_total": len(sentences),
        "sentences_needing_citation": total_needs_citation,
        "supported": supported,
        "partially_supported": partially,
        "unsupported": unsupported,
        "uncited_factual_sentences": uncited,
        "commentary_skipped": commentary,
        "support_rate_strict": strict_rate,
        "details": results,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.agents.verify_citations <section_number>")
        sys.exit(1)

    section_number = int(sys.argv[1])

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM drafts WHERE section_number = ? ORDER BY id DESC LIMIT 1",
        (section_number,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        print("No draft found for section {0}".format(section_number))
        sys.exit(1)

    text = row["content"]
    result = verify_draft(text, section_number)
    print(json.dumps(result, ensure_ascii=False, indent=2))