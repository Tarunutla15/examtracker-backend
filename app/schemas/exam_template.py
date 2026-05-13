from typing import Literal

from pydantic import BaseModel, Field


class StructuredExamTemplateExtraction(BaseModel):
    exam_name: str | None = None
    sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    extraction_quality: Literal["high", "medium", "low"] | None = None


class ExamTemplateExtractResponse(StructuredExamTemplateExtraction):
    raw_text: str = ""
    provider: str | None = None


class ExamTemplateTextRequest(BaseModel):
    text: str = Field(min_length=1)
