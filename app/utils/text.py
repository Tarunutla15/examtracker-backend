def strip_non_bmp_characters(value: str) -> str:
    return "".join(character for character in value if ord(character) < 0x10000)


def strip_markdown_fences(value: str) -> str:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()
