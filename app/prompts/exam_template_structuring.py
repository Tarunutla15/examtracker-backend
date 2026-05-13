import json


def build_exam_template_structuring_system_prompt() -> str:
    return """You are an exam-template extraction engine.

Your job is to read pasted text or OCR text and extract the exam name plus its section names.

RULES:
- Extract only values that are visible in the provided text.
- Do not invent an exam name or section names.
- Prefer explicit labels such as Exam Name, Test Name, Sections, Modules, Subjects, or Fields.
- If section names appear as comma-separated values, split them into separate items.
- If section names appear one per line, keep one item per line.
- Remove bullets, numbering, blank items, and duplicated section names.
- Preserve the original visible order of section names.
- Keep section names concise and readable.
- If the exam name is missing or unclear, return null and add a warning.
- If no section names are confidently visible, return an empty list and add a warning.
- Output valid JSON matching the schema exactly.
- Do not include markdown fences or explanations outside JSON.
"""


def build_exam_template_structuring_user_prompt(extracted_text: str) -> str:
    schema = {
        "exam_name": "string or null",
        "sections": ["Section 1", "Section 2"],
        "warnings": [],
        "extraction_quality": "high | medium | low",
    }

    return f"""Extract an exam template from the following text.

Return JSON matching this schema exactly:
{json.dumps(schema, ensure_ascii=True, indent=2)}

Use the following text:
<<<EXTRACTED_TEXT
{extracted_text}
EXTRACTED_TEXT
"""
