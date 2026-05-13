from typing import Literal

from pydantic import BaseModel, Field


class OCRSummarySectionResult(BaseModel):
    name: str
    questions: int | None = None
    answered: int | None = None
    not_answered: int | None = None
    review: int | None = None
    mark_for_review: int | None = None
    not_visited: int | None = None
    time_spent: str | None = None
    summary_found: bool = False
    notes: list[str] = Field(default_factory=list)


class OCRResultSectionResult(BaseModel):
    name: str
    questions: int | None = None
    correct: int | None = None
    wrong: int | None = None
    correct_marks: float | None = None
    wrong_marks: float | None = None
    total_marks: float | None = None
    accuracy_percentage: float | None = None
    result_found: bool = False
    notes: list[str] = Field(default_factory=list)


class StructuredExamExtraction(BaseModel):
    exam_name: str | None = None
    test_date: str | None = None
    summary_sections: list[OCRSummarySectionResult]
    result_sections: list[OCRResultSectionResult]
    warnings: list[str] = Field(default_factory=list)
    extraction_quality: Literal["high", "medium", "low"] | None = None


class OCRExtractResponse(StructuredExamExtraction):
    raw_text: str = ""
    provider: str | None = None
