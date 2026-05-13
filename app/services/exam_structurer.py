import logging
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from app.core.config import get_settings
from app.prompts.exam_structuring import (
    build_exam_structuring_system_prompt,
    build_exam_structuring_user_prompt,
)
from app.schemas.exam_ocr import (
    OCRResultSectionResult,
    OCRSummarySectionResult,
    StructuredExamExtraction,
)
from app.utils.text import strip_non_bmp_characters


logger = logging.getLogger("examtracker.ocr")


class StructuringError(RuntimeError):
    pass


@lru_cache
def get_structuring_llm():
    settings = get_settings()
    if settings.ocr_provider == "groq":
        if not settings.groq_api_key:
            raise StructuringError("GROQ_API_KEY is missing for exam structuring.")

        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_structuring_model,
            temperature=0,
            timeout=settings.request_timeout_seconds,
        )

    if settings.ocr_provider == "openai":
        if not settings.openai_api_key:
            raise StructuringError("OPENAI_API_KEY is missing for exam structuring.")

        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_structuring_model,
            temperature=0,
            timeout=settings.request_timeout_seconds,
        )

    raise StructuringError(
        f"OCR provider '{settings.ocr_provider}' is not implemented. Use 'groq' or 'openai'."
    )


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return strip_non_bmp_characters(value)


def _sanitize_structured_output(result: StructuredExamExtraction) -> StructuredExamExtraction:
    sanitized_summary_sections = [
        OCRSummarySectionResult(
            name=_sanitize_text(section.name) or "",
            questions=section.questions,
            answered=section.answered,
            not_answered=section.not_answered,
            review=section.review,
            mark_for_review=section.mark_for_review,
            not_visited=section.not_visited,
            time_spent=_sanitize_text(section.time_spent),
            summary_found=section.summary_found,
            notes=[_sanitize_text(note) or "" for note in section.notes if _sanitize_text(note)],
        )
        for section in result.summary_sections
    ]

    sanitized_result_sections = [
        OCRResultSectionResult(
            name=_sanitize_text(section.name) or "",
            questions=section.questions,
            correct=section.correct,
            wrong=section.wrong,
            correct_marks=section.correct_marks,
            wrong_marks=section.wrong_marks,
            total_marks=section.total_marks,
            accuracy_percentage=section.accuracy_percentage,
            result_found=section.result_found,
            notes=[_sanitize_text(note) or "" for note in section.notes if _sanitize_text(note)],
        )
        for section in result.result_sections
    ]

    return StructuredExamExtraction(
        exam_name=_sanitize_text(result.exam_name),
        test_date=_sanitize_text(result.test_date),
        summary_sections=sanitized_summary_sections,
        result_sections=sanitized_result_sections,
        warnings=[_sanitize_text(warning) or "" for warning in result.warnings if _sanitize_text(warning)],
        extraction_quality=result.extraction_quality,
    )


def _align_summary_sections_to_requested_names(
    extracted_sections: list[OCRSummarySectionResult],
    requested_sections: list[str],
) -> list[OCRSummarySectionResult]:
    normalized_lookup = {
        section.name.strip().lower(): section
        for section in extracted_sections
    }

    aligned_sections: list[OCRSummarySectionResult] = []
    for requested_section in requested_sections:
        match = normalized_lookup.get(requested_section.strip().lower())
        if match:
            match.name = requested_section
            aligned_sections.append(match)
            continue

        aligned_sections.append(
            OCRSummarySectionResult(
                name=requested_section,
                notes=["Section was not confidently extracted from the uploaded documents."],
            )
        )

    return aligned_sections


def _align_result_sections_to_requested_names(
    extracted_sections: list[OCRResultSectionResult],
    requested_sections: list[str],
) -> list[OCRResultSectionResult]:
    normalized_lookup = {
        section.name.strip().lower(): section
        for section in extracted_sections
    }

    aligned_sections: list[OCRResultSectionResult] = []
    for requested_section in requested_sections:
        match = normalized_lookup.get(requested_section.strip().lower())
        if match:
            match.name = requested_section
            aligned_sections.append(match)
            continue

        aligned_sections.append(
            OCRResultSectionResult(
                name=requested_section,
                notes=["Section was not confidently extracted from the uploaded documents."],
            )
        )

    return aligned_sections


def structure_exam_document(
    exam_name: str | None,
    sections: list[str],
    extracted_text: str,
) -> StructuredExamExtraction:
    llm = get_structuring_llm().with_structured_output(StructuredExamExtraction)
    messages = [
        SystemMessage(content=build_exam_structuring_system_prompt()),
        HumanMessage(
            content=build_exam_structuring_user_prompt(
                exam_name=exam_name,
                section_names=sections,
                extracted_text=extracted_text,
            )
        ),
    ]

    logger.info("Structuring OCR text with LLM for %d requested sections", len(sections))
    result = llm.invoke(messages)
    if not isinstance(result, StructuredExamExtraction):
        raise StructuringError("LLM did not return a valid structured exam extraction.")

    sanitized_result = _sanitize_structured_output(result)
    sanitized_result.summary_sections = _align_summary_sections_to_requested_names(
        sanitized_result.summary_sections,
        sections,
    )
    sanitized_result.result_sections = _align_result_sections_to_requested_names(
        sanitized_result.result_sections,
        sections,
    )
    return sanitized_result
