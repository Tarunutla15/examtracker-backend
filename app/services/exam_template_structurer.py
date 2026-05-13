import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts.exam_template_structuring import (
    build_exam_template_structuring_system_prompt,
    build_exam_template_structuring_user_prompt,
)
from app.schemas.exam_template import StructuredExamTemplateExtraction
from app.services.exam_structurer import StructuringError, get_structuring_llm
from app.utils.text import strip_non_bmp_characters


logger = logging.getLogger("examtracker.ocr")

_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[\).\-\s]+|[A-Za-z][\).\-\s]+)\s*")
_SECTION_LABEL_RE = re.compile(
    r"^\s*(?:sections?|fields?|modules?|subjects?)\s*[:\-]?\s*(.*)$",
    flags=re.IGNORECASE,
)
_EXAM_LABEL_RE = re.compile(
    r"^\s*(?:exam\s*name|test\s*name|exam|name)\s*[:\-]\s*(.+)$",
    flags=re.IGNORECASE,
)


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    return strip_non_bmp_characters(value).strip()


def _normalize_exam_name(value: str | None) -> str | None:
    cleaned_value = _sanitize_text(value)
    if not cleaned_value:
        return None

    cleaned_value = _BULLET_PREFIX_RE.sub("", cleaned_value).strip(" \t:-")
    return re.sub(r"\s+", " ", cleaned_value).strip() or None


def _normalize_section_name(value: str | None) -> str | None:
    cleaned_value = _sanitize_text(value)
    if not cleaned_value:
        return None

    cleaned_value = _BULLET_PREFIX_RE.sub("", cleaned_value)
    cleaned_value = re.sub(
        r"^\s*(?:section|field|module|subject)\s*[:\-]\s*",
        "",
        cleaned_value,
        flags=re.IGNORECASE,
    )
    cleaned_value = re.sub(r"\s+", " ", cleaned_value).strip(" \t,;|-")
    return cleaned_value or None


def _dedupe_sections(sections: list[str]) -> list[str]:
    unique_sections: list[str] = []
    seen: set[str] = set()

    for section in sections:
        normalized_section = _normalize_section_name(section)
        if not normalized_section:
            continue

        lookup_key = normalized_section.lower()
        if lookup_key in seen:
            continue

        seen.add(lookup_key)
        unique_sections.append(normalized_section)

    return unique_sections


def _split_section_values(value: str) -> list[str]:
    cleaned_value = value.strip()
    if not cleaned_value:
        return []

    if "|" in cleaned_value:
        return [part.strip() for part in cleaned_value.split("|") if part.strip()]

    if any(separator in cleaned_value for separator in [",", ";"]):
        return [part.strip() for part in re.split(r"[;,]", cleaned_value) if part.strip()]

    return [cleaned_value]


def _heuristic_extract_exam_template(extracted_text: str) -> StructuredExamTemplateExtraction | None:
    raw_lines = [strip_non_bmp_characters(line).strip() for line in extracted_text.splitlines()]
    lines = [line for line in raw_lines if line]
    if not lines:
        return None

    exam_name: str | None = None
    candidate_section_lines: list[str] = []
    collecting_sections = False

    for line in lines:
        exam_match = _EXAM_LABEL_RE.match(line)
        if exam_match and not exam_name:
            exam_name = _normalize_exam_name(exam_match.group(1))
            collecting_sections = False
            continue

        section_match = _SECTION_LABEL_RE.match(line)
        if section_match:
            collecting_sections = True
            inline_value = section_match.group(1).strip()
            if inline_value:
                candidate_section_lines.extend(_split_section_values(inline_value))
            continue

        if line.upper().startswith("SECTION|"):
            collecting_sections = True
            candidate_section_lines.append(line.split("|", 1)[1].strip())
            continue

        if line.upper().startswith("EXAM_NAME:") and not exam_name:
            exam_name = _normalize_exam_name(line.split(":", 1)[1])
            continue

        if collecting_sections:
            candidate_section_lines.extend(_split_section_values(line))
            continue

        candidate_section_lines.append(line)

    if not exam_name and candidate_section_lines:
        exam_name = _normalize_exam_name(candidate_section_lines[0])
        candidate_section_lines = candidate_section_lines[1:]

    sections = _dedupe_sections(candidate_section_lines)
    if not exam_name and not sections:
        return None

    warnings: list[str] = []
    if not exam_name:
        warnings.append("Exam name was not clearly identified from the provided text.")
    if not sections:
        warnings.append("No section names were confidently identified from the provided text.")

    quality = "high" if exam_name and sections else "medium"
    return StructuredExamTemplateExtraction(
        exam_name=exam_name,
        sections=sections,
        warnings=warnings,
        extraction_quality=quality,
    )


def _sanitize_structured_output(
    result: StructuredExamTemplateExtraction,
) -> StructuredExamTemplateExtraction:
    sanitized_exam_name = _normalize_exam_name(result.exam_name)
    sanitized_sections = _dedupe_sections(result.sections)
    sanitized_warnings = [
        warning for warning in (_sanitize_text(warning) for warning in result.warnings) if warning
    ]

    if not sanitized_exam_name:
        sanitized_warnings.append("Exam name was not clearly identified from the provided text.")

    if not sanitized_sections:
        sanitized_warnings.append("No section names were confidently identified from the provided text.")

    deduped_warnings: list[str] = []
    seen_warnings: set[str] = set()
    for warning in sanitized_warnings:
        warning_key = warning.lower()
        if warning_key in seen_warnings:
            continue
        seen_warnings.add(warning_key)
        deduped_warnings.append(warning)

    quality = result.extraction_quality
    if not sanitized_sections:
        quality = "low"
    elif not sanitized_exam_name and quality == "high":
        quality = "medium"

    return StructuredExamTemplateExtraction(
        exam_name=sanitized_exam_name,
        sections=sanitized_sections,
        warnings=deduped_warnings,
        extraction_quality=quality,
    )


def structure_exam_template(
    extracted_text: str,
    prefer_simple_parse: bool = False,
) -> StructuredExamTemplateExtraction:
    if prefer_simple_parse:
        heuristic_result = _heuristic_extract_exam_template(extracted_text)
        if heuristic_result and heuristic_result.sections:
            return heuristic_result

    llm = get_structuring_llm().with_structured_output(StructuredExamTemplateExtraction)
    messages = [
        SystemMessage(content=build_exam_template_structuring_system_prompt()),
        HumanMessage(content=build_exam_template_structuring_user_prompt(extracted_text)),
    ]

    logger.info("Structuring exam-template text with LLM")
    result = llm.invoke(messages)
    if not isinstance(result, StructuredExamTemplateExtraction):
        raise StructuringError("LLM did not return a valid exam template extraction.")

    sanitized_result = _sanitize_structured_output(result)
    if sanitized_result.sections:
        return sanitized_result

    heuristic_fallback = _heuristic_extract_exam_template(extracted_text)
    if heuristic_fallback:
        return heuristic_fallback

    return sanitized_result
