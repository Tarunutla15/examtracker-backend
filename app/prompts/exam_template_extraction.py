def build_exam_template_document_extraction_prompt() -> str:
    return """You are extracting text from an exam setup image or PDF for an ExamTracker app.

Your goal is to capture the exam name and the section names as accurately as possible.

FOCUS ON:
- exam name or test name
- section, module, field, or subject names
- short labels near the exam setup content

IGNORE IF PRESENT:
- advertisements
- navigation text
- question-by-question answer keys
- score history
- repeated page chrome

OUTPUT FORMAT:
Return plain text in this exact structure:

EXAM_NAME: <value or Not found>

SECTIONS:
SECTION|<section name>
SECTION|<section name>
SECTION|...

ADDITIONAL_NOTES:
- <short note only if something is unclear>

RULES:
- Keep one section per SECTION line.
- Preserve visible order.
- Do not invent section names.
- If a section is unclear, use best effort and keep it short.
- Do not return JSON.
- Do not include markdown fences.
"""
