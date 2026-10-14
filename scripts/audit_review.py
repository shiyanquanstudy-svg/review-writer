import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

REVIEW_PATH = Path(__file__).resolve().parent.parent / "data" / "review_output.md"


def main():
    text = REVIEW_PATH.read_text(encoding="utf-8")

    # Split at "## 参考文献"
    if "## 参考文献" not in text:
        print("ERROR: 参考文献 section not found")
        return

    body, refs_section = text.split("## 参考文献", 1)

    # Remove [Sources: ...] tail markers from body
    body = re.sub(r"\[Sources:[^\]]*\]", "", body)

    # Citations in body
    body_citations = set(re.findall(r"\[(pubmed_\d+|ct_[A-Z0-9]+)\]", body))

    # Source IDs in reference list (via URLs and NCT identifiers)
    ref_pubmed = set("pubmed_" + m for m in re.findall(
        r"https://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/", refs_section))
    ref_ct = set("ct_" + m for m in re.findall(
        r"ClinicalTrials\.gov identifier:\s*([A-Z0-9]+)", refs_section))
    ref_citations = ref_pubmed | ref_ct

    print("=" * 60)
    print("CITATION AUDIT")
    print("=" * 60)
    print("Body unique citations:  {0}".format(len(body_citations)))
    print("Reference list entries: {0}".format(len(ref_citations)))
    print()

    # Cited in body but not in reference list
    missing_in_refs = body_citations - ref_citations
    if missing_in_refs:
        print("[PROBLEM] Cited in body but MISSING from reference list:")
        for sid in sorted(missing_in_refs):
            print("  {0}".format(sid))
    else:
        print("[OK] Every body citation appears in the reference list.")
    print()

    # Listed in reference list but never cited in body
    orphan_refs = ref_citations - body_citations
    if orphan_refs:
        print("[WARNING] In reference list but NOT cited in body:")
        for sid in sorted(orphan_refs):
            print("  {0}".format(sid))
    else:
        print("[OK] Every reference is cited in the body.")
    print()

    # Check duplicate reference numbers (rough)
    ref_numbers = re.findall(r"(?m)^(\d+)\.\s", refs_section)
    if ref_numbers:
        print("Reference numbers: {0} entries, 1..{1}".format(
            len(ref_numbers), max(int(n) for n in ref_numbers)))
        expected = set(range(1, len(ref_numbers) + 1))
        actual = set(int(n) for n in ref_numbers)
        if expected != actual:
            print("[WARNING] Reference numbering is not contiguous")
        else:
            print("[OK] Reference numbering is contiguous 1..{0}".format(len(ref_numbers)))


if __name__ == "__main__":
    main()