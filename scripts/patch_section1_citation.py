import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.db_helper import get_conn


def main():
    conn = get_conn()
    cur = conn.cursor()

    # Get latest Section 1 draft
    cur.execute(
        "SELECT id, content FROM drafts WHERE section_number = 1 ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    if row is None:
        print("No Section 1 draft found")
        return

    old_content = row["content"]
    draft_id = row["id"]

    # Fix 1: 5%/27.6% should cite pubmed_36614020 not pubmed_38490591
    old_sentence = (
        "世界卫生组织曾估计全球患病率约为5%，然而新近研究报告的患病率可高达27.6%，"
        "提示不同调查口径与人群背景下患病率估计存在显著差异[pubmed_38490591]"
    )
    new_sentence = (
        "世界卫生组织曾估计全球患病率约为5%，然而新近研究报告的患病率可高达27.6%，"
        "提示不同调查口径与人群背景下患病率估计存在显著差异[pubmed_36614020]"
    )

    if old_sentence in old_content:
        new_content = old_content.replace(old_sentence, new_sentence)
        print("Fixed: 5%/27.6% citation corrected")
    else:
        print("WARNING: target sentence not found, trying simpler replace")
        new_content = old_content.replace(
            "存在显著差异[pubmed_38490591]",
            "存在显著差异[pubmed_36614020]",
        )
        if new_content == old_content:
            print("FAILED: no replacement made")

    # Update DB
    cur.execute(
        "UPDATE drafts SET content = ? WHERE id = ?",
        (new_content, draft_id),
    )
    conn.commit()
    conn.close()

    print("Patched draft id={0}".format(draft_id))
    print("Old length: {0}, new length: {1}".format(len(old_content), len(new_content)))


if __name__ == "__main__":
    main()