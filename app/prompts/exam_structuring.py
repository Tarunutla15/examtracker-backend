import json


def build_exam_structuring_system_prompt() -> str:
    return """You are an exam-result structuring engine.

Your job is to convert extracted exam-result text into strict JSON for an ExamTracker form.

RULES:
- Extract ONLY values that are visible in the extracted text.
- Never invent missing values.
- Prefer `SUMMARY_ROW|...` and `RESULT_ROW|...` lines over every other text fragment.
- Ignore key sheets, question-by-question answer rows, dashboard text, or history tables.
- Preserve the provided section names exactly as they are given.
- Never create extra section names outside the provided list.
- If the extracted text uses slightly different wording, map it to the closest provided section name.
- If a value is missing or unclear, return null for that field and explain it in notes.
- Use integers for numeric counts.
- Use time in HH:MM:SS format.
- Use test_date in YYYY-MM-DD format when a date is clearly visible.
- Mark summary_found true only if summary fields were found for that section.
- Mark result_found true only if result fields were found for that section.
- Keep warnings focused on real ambiguity, conflicts, or missing sections.
- Output must be valid JSON matching the schema.
- Do not include markdown fences or explanations outside JSON.

Character constraints:
- Remove non-BMP characters.
- Use UTF-8 safe text.

Validation guidance:
- Summary values should come from SUMMARY_ROW lines.
- Result values should come from RESULT_ROW lines.
- Ignore rows whose module name is Total when filling section rows.
- If a result row cell is ambiguous, prefer the value that best matches the labeled row and visible accuracy/marks, but do not invent unseen numbers.
- For these mock tests, assume scoring is usually `+1` for each correct answer and `-0.25` for each wrong answer unless the row clearly shows a different rule.
- Use arithmetic consistency checks when PDF columns shift:
  1. `correct + wrong` should usually be less than or equal to `answered`
  2. `accuracy percentage` should usually match `correct / answered * 100`
  3. `total marks` should usually match `correct - 0.25 * wrong`
  4. `wrong marks` should usually match `wrong * 0.25`
  5. `correct marks` should usually match `correct`
- If the extracted row has conflicting cells, choose the integer `correct` and `wrong` values that best satisfy the visible marks/accuracy/answered constraints and mention the correction in notes.
- Return summary and result as separate section arrays so the frontend can fill each table independently.
"""


def build_exam_structuring_user_prompt(
    exam_name: str | None,
    section_names: list[str],
    extracted_text: str,
) -> str:
    schema = {
        "exam_name": exam_name or None,
        "test_date": "YYYY-MM-DD or null",
        "summary_sections": [
            {
                "name": section_name,
                "questions": 0,
                "answered": 0,
                "not_answered": 0,
                "review": 0,
                "mark_for_review": 0,
                "not_visited": 0,
                "time_spent": "HH:MM:SS or null",
                "summary_found": False,
                "notes": [],
            }
            for section_name in section_names
        ],
        "result_sections": [
            {
                "name": section_name,
                "questions": 0,
                "correct": 0,
                "wrong": 0,
                "correct_marks": 0.0,
                "wrong_marks": 0.0,
                "total_marks": 0.0,
                "accuracy_percentage": 0.0,
                "result_found": False,
                "notes": [],
            }
            for section_name in section_names
        ],
        "warnings": [],
        "extraction_quality": "high | medium | low",
    }

    return f"""Extract exam data for the selected test.

Selected exam name:
{exam_name or "Not provided"}

Expected sections:
{json.dumps(section_names, ensure_ascii=True)}

Return JSON matching this schema exactly:
{json.dumps(schema, ensure_ascii=True, indent=2)}

Use the following extracted document text:
<<<EXTRACTED_TEXT
{extracted_text}
EXTRACTED_TEXT
"""
