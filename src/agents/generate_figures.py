import re
import json
import textwrap
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from src.llm import call_llm_json
from src.agents.language_utils import is_english

FIGURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def _get_font(language: str):
    if is_english(language):
        return None
    candidates = [
        "Microsoft YaHei", "SimHei", "PingFang SC",
        "Noto Sans CJK SC", "WenQuanYi Zen Hei",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            return c
    return None


def _normalize_name(name: str) -> str:
    """Lowercase + strip spaces and hyphens for dedup comparison."""
    return re.sub(r"[\s\-_]", "", (name or "").lower())


def _dedupe_items(items: list) -> list:
    """Keep first occurrence of each normalized name, preserve order."""
    seen = set()
    result = []
    for it in items:
        key = _normalize_name(it)
        if key and key not in seen:
            seen.add(key)
            result.append(it)
    return result


def extract_milestones(section_text: str) -> list:
    prompt = """Extract a chronological list of key development milestones from the following text.

Text:
{text}

Output JSON:
{{
  "milestones": [
    {{"date": "YYYY or YYYY-MM or empty string", "label": "short milestone description (STRICT: <= 40 chars)"}}
  ]
}}

Rules:
- Include milestones describing: new tracers introduced, new chemical classes, key findings, regulatory approvals, clinical milestones.
- If a specific date is mentioned in the text, use it (format: YYYY or YYYY-MM).
- If no date is mentioned, use an empty string "" for date.
- label: STRICT MAXIMUM 40 characters. Count carefully. Short noun phrases preferred.
- Maximum 9 milestones. Keep the most important ones.
- Order: if dates available, chronological; otherwise logical order of development.
- Do NOT invent dates or facts.

Output ONLY JSON."""

    result = call_llm_json(prompt.format(text=section_text[:4000]), temperature=0.1)
    milestones = result.get("milestones", [])
    # Hard truncate as a safety net
    for m in milestones:
        m["label"] = (m.get("label") or "")[:40]
    return milestones


def draw_milestone_flow(milestones: list, out_path: Path, title: str, language: str) -> bool:
    if not milestones:
        return False

    font = _get_font(language)
    if font:
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False

    n = len(milestones)
    has_dates = any((m.get("date") or "").strip() for m in milestones)

    # Dynamic width: minimum 14 inches, scale with number of milestones
    fig_width = max(14, n * 1.8)
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    xs = list(range(n))
    ax.plot(xs, [0] * n, "k-", linewidth=2, zorder=1)
    ax.scatter(xs, [0] * n, s=140, c="#1f6feb", zorder=2)

    for i, m in enumerate(milestones):
        y_offset = 0.85 if i % 2 == 0 else -0.85
        va = "bottom" if y_offset > 0 else "top"
        date = (m.get("date") or "").strip()
        label = (m.get("label") or "")[:40]
        wrapped = textwrap.fill(label, width=22)

        if has_dates and date:
            header = date
        else:
            header = "Step {0}".format(i + 1)
        text = "{0}\n{1}".format(header, wrapped)

        ax.text(
            i, y_offset, text, ha="center", va=va, fontsize=9,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#f0f6ff",
                      edgecolor="#1f6feb", linewidth=1),
        )

    ax.set_ylim(-2.2, 2.2)
    ax.set_xlim(-0.6, n - 0.4)
    ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def extract_classification(section_text: str) -> dict:
    prompt = """Extract a two-level classification of items from the following text.

Text:
{text}

Output JSON:
{{
  "root": "root label (<= 30 chars)",
  "categories": [
    {{"name": "category name (<= 30 chars)", "items": ["item 1", "item 2"]}}
  ]
}}

Rules:
- categories: 2-4 categories.
- items: 2-8 items per category, each <= 30 chars.
- Only use names that explicitly appear in the text.
- Do NOT invent items.
- DEDUPLICATION (important): [18F]THK5351 and [18F]THK-5351 are the SAME compound; [18F]AV1451 and [18F]AV-1451 are the SAME compound. Pick ONE canonical form (prefer the form with explicit hyphen, e.g. [18F]THK-5351). If two items refer to the same entity, keep only one.
- Normalize: keep "T807" and "[18F]AV-1451" as separate entries only if they are genuinely treated as separate in the text.

Output ONLY JSON."""

    data = call_llm_json(prompt.format(text=section_text[:4000]), temperature=0.1)

    # Post-process dedup per category
    for cat in data.get("categories", []):
        cat["items"] = _dedupe_items(cat.get("items", []))

    return data


def draw_classification_tree(data: dict, out_path: Path, title: str, language: str) -> bool:
    categories = data.get("categories", [])
    if not categories:
        return False

    font = _get_font(language)
    if font:
        plt.rcParams["font.sans-serif"] = [font]
        plt.rcParams["axes.unicode_minus"] = False

    max_items = max((len(c.get("items", [])) for c in categories), default=1)
    fig_height = max(6, max_items * 0.55 + 3)

    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.axis("off")

    ax.text(
        0.5, 0.98, data.get("root", ""), ha="center", va="top", fontsize=13, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#dbeafe",
                  edgecolor="#1f6feb", linewidth=2),
        transform=ax.transAxes,
    )

    n = len(categories)
    x_positions = [(i + 1) / (n + 1) for i in range(n)]

    for x, cat in zip(x_positions, categories):
        ax.plot([0.5, x], [0.88, 0.74], "k-", linewidth=1.5, transform=ax.transAxes)
        ax.text(
            x, 0.72, cat.get("name", ""), ha="center", va="top", fontsize=11,
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#e0e7ff",
                      edgecolor="#6366f1", linewidth=1),
            transform=ax.transAxes,
        )

        items = cat.get("items", [])
        for j, item in enumerate(items):
            y = 0.60 - j * (0.50 / max_items)
            ax.plot([x, x], [0.63, y + 0.012], "k-", linewidth=0.8,
                    transform=ax.transAxes)
            ax.text(
                x + 0.012, y, "  " + item, ha="left", va="center", fontsize=9,
                transform=ax.transAxes,
            )

    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


def generate_all_figures(drafts: dict, language: str, spec_title: str = "") -> dict:
    results = {}

    timeline_text = ""
    for k in [2, 3]:
        if k in drafts and drafts[k]:
            timeline_text += drafts[k] + "\n\n"

    if timeline_text:
        try:
            milestones = extract_milestones(timeline_text)
            if milestones:
                out = FIGURES_DIR / "timeline.png"
                ok = draw_milestone_flow(milestones, out, "Development Milestones", language)
                if ok:
                    results["timeline"] = "data/figures/timeline.png"
                    print("[figure] timeline with {0} milestones".format(len(milestones)))
        except Exception as e:
            print("[figure] timeline failed: {0}".format(e))

    if 2 in drafts and drafts[2]:
        try:
            data = extract_classification(drafts[2])
            if data.get("categories"):
                out = FIGURES_DIR / "classification.png"
                ok = draw_classification_tree(data, out, "Classification of Tracers", language)
                if ok:
                    results["classification"] = "data/figures/classification.png"
                    print("[figure] classification with {0} categories".format(len(data["categories"])))
        except Exception as e:
            print("[figure] classification failed: {0}".format(e))

    return results


if __name__ == "__main__":
    from src.db.db_helper import get_conn
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT section_number, content FROM drafts d1
        WHERE id = (SELECT MAX(id) FROM drafts d2 WHERE d2.section_number = d1.section_number)
        ORDER BY section_number
    """)
    drafts = {row["section_number"]: row["content"] for row in cur.fetchall()}
    conn.close()

    figures = generate_all_figures(drafts, "English", "Test")
    print(json.dumps(figures, indent=2))