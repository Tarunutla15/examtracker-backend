import json


def build_exam_structuring_system_prompt() -> str:
    return """You are an exam-result structuring engine.

Your job is to convert extracted exam-result text into strict JSON for an ExamTracker form.

RULES:
- Extract ONLY values that are visible in the extracted text.
- Never invent missing values.
- Prefer `SUMMARY_ROW|...` and `RESULT_ROW|...` lines over every other text fragment.
- Table column meaning comes from the PDF: when `SUMMARY_HEADER|` or `RESULT_HEADER|` lines are present, treat them as authoritative. Map each data cell to schema fields by matching that column's header label (case-insensitive, allow minor OCR typos), not by fixed column position — exams reorder and rename columns.
- For result rows, map headers to fields using meaning, for example: module name -> section matching; "correct"/"right"/"good"/"no correct" style labels -> `correct` (integer count); "wrong"/"incorrect"/"bad"/"no wrong" -> `wrong`; "correct marks"/"marks for correct"/"positive"/"gain" -> `correct_marks`; "wrong marks"/"negative marks"/"penalty"/"marks lost" -> `wrong_marks`; "total marks"/"net"/"score"/"obtained"/"final marks" -> `total_marks`; "accuracy"/"%" -> `accuracy_percentage`; "questions"/"attempted"/"total ques" in the result block -> `questions` when that column exists.
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
- Summary values should come from SUMMARY_ROW lines aligned with SUMMARY_HEADER when present.
- Result values should come from RESULT_ROW lines aligned with RESULT_HEADER when present.
- Ignore rows whose module name is Total when filling section rows.
- If a result row cell is ambiguous, prefer the value that best matches the labeled row and visible accuracy/marks, but do not invent unseen numbers.
- Infer the scoring rule from visible marks and counts when possible (e.g. `correct_marks / correct`, `wrong_marks / wrong`). If the PDF implies a different rule than +1 / -0.25, trust the PDF numbers for `correct_marks`, `wrong_marks`, and `total_marks`, and set integer `correct`/`wrong` from count columns when present; only use arithmetic to resolve conflicts, and note assumptions in notes.
- Use consistency checks using header-mapped fields (not column index):
  1. `correct + wrong` should usually be less than or equal to `answered` from the summary for that section when both exist
  2. When `accuracy_percentage` exists, it should usually align with `correct` and attempted counts from the document
  3. When marks columns exist, `total_marks` should usually align with `correct_marks - wrong_marks` if both components are visible as penalties
- If count columns and marks columns disagree (common after OCR shifts), prefer the values whose header labels clearly identify them; if still ambiguous, prefer marks-derived consistency with labeled totals and mention the correction in notes.
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
