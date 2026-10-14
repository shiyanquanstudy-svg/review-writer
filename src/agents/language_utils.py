def is_english(language: str) -> bool:
    lang = (language or "").strip().lower()
    return "english" in lang or lang == "en" or lang.startswith("en-")


def writer_language_instruction(language: str) -> str:
    """Instruction for section writing."""
    if is_english(language):
        return (
            "Write the section in formal academic English. "
            "Use standard scientific terminology. "
            "Keep all [source_id] citation markers unchanged (do NOT translate them). "
            "Use SI units and standard gene/protein nomenclature."
        )
    return (
        "请用正式学术中文写作，使用标准科学术语。"
        "引用标记 [source_id] 保持原样，不要翻译。"
    )


def outline_language_instruction(language: str) -> str:
    """Instruction for outline fields."""
    if is_english(language):
        return "Write thesis and key_points in formal academic English."
    return "thesis 和 key_points 使用正式学术中文撰写。"


def abstract_language_instruction(language: str) -> str:
    """Instruction for the abstract."""
    if is_english(language):
        return (
            "Write the abstract in formal academic English. "
            "250-350 words, single paragraph, no headings. "
            "Keep [source_id] markers unchanged."
        )
    return (
        "摘要使用正式学术中文撰写，250-350字，单段落，不含小标题。"
        "[source_id] 标记保持原样。"
    )