import json


def build_exam_document_extraction_prompt(
    exam_name: str | None,
    section_names: list[str],
) -> str:
    return f"""You are extracting data from a mock-test exam PDF or screenshot for an ExamTracker app.

Your job is to extract ONLY the information needed to fill the test-entry form.

Selected exam:
{exam_name or "Not provided"}

Expected section names:
{json.dumps(section_names, ensure_ascii=True)}

PRIORITY:
1. Exam Summary table
2. Result table
3. Exam/test name
4. Test date

IGNORE THESE IF PRESENT:
- key sheet
- question-by-question answers
- dashboard/history tables
- advertisements
- navigation text
- repeated page chrome

GOLDEN RULES:
1. Extract ONLY what is visibly present in the summary/result tables and nearby exam metadata.
2. Do not invent rows or values.
3. Preserve row order.
4. Use best-effort reading for unclear cells.
5. If a section name in the PDF differs slightly, keep the visible name as extracted.
6. Do not return JSON.

OUTPUT FORMAT:
Return plain text in this exact structure:

EXAM_NAME: <value or Not found>
TEST_DATE: <value or Not found>

SUMMARY_TABLE:
SUMMARY_HEADER|Module Name|Questions|Answered|Not Answered|Review|Mark For Review|Not Visited|Time Spent
SUMMARY_ROW|<module>|<questions>|<answered>|<not answered>|<review>|<mark for review>|<not visited>|<time>
SUMMARY_ROW|...

RESULT_TABLE:
RESULT_HEADER|Module Name|Correct|Wrong|Correct Marks|Wrong Marks|Total Marks|Accuracy Percentage
RESULT_ROW|<module>|<correct>|<wrong>|<correct marks>|<wrong marks>|<total marks>|<accuracy percentage>
RESULT_ROW|...

If a total row is visible, include it too using SUMMARY_ROW or RESULT_ROW with module name Total.

EXTRACTION RULES:
- Keep one row per line.
- Preserve visible column order.
- Use the actual visible row values from the PDF.
- If a cell is unreadable, use your best effort and add [?] only on that cell value.
- Do NOT include question-by-question answer keys.
- Do NOT include long raw OCR dumps outside this structure.

Finish with:
---EXTRACTION SUMMARY---
Document Type: exam result
Exam Name: [name or "Not found"]
Test Date: [date or "Not found"]
Sections Found: [comma-separated section names from summary/result rows or "Not found"]
Summary Table Present: [yes or no]
Result Table Present: [yes or no]
---END SUMMARY---
"""
