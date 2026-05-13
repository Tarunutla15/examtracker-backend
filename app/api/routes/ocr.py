import json
import logging
from time import perf_counter

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas.exam_template import ExamTemplateExtractResponse, ExamTemplateTextRequest
from app.schemas.exam_ocr import OCRExtractResponse
from app.services.document_extractor import (
    DocumentExtractionError,
    DocumentInput,
    combine_document_texts,
    extract_text_from_document,
)
from app.services.exam_template_structurer import structure_exam_template
from app.services.exam_structurer import StructuringError, structure_exam_document


logger = logging.getLogger("examtracker.ocr")
router = APIRouter()


def _parse_sections_payload(sections: str) -> list[str]:
    try:
        parsed_sections = json.loads(sections)
    except json.JSONDecodeError as error:
        logger.warning("Received invalid sections payload")
        raise HTTPException(status_code=400, detail="Invalid sections payload") from error

    if not isinstance(parsed_sections, list) or not all(isinstance(item, str) for item in parsed_sections):
        logger.warning("Received malformed sections payload: %s", parsed_sections)
        raise HTTPException(status_code=400, detail="Sections must be a JSON string array")

    return parsed_sections


async def _extract_text_from_uploads(
    files: list[UploadFile],
    exam_name: str | None = None,
    section_names: list[str] | None = None,
    extraction_target: str = "test_result",
) -> list[tuple[str, str]]:
    if not files:
        logger.warning("OCR request rejected because no files were uploaded")
        raise HTTPException(status_code=400, detail="At least one file is required")

    extracted_documents: list[tuple[str, str]] = []
    for index, upload in enumerate(files, start=1):
        file_name = upload.filename or f"upload-{index}"
        contents = await upload.read()
        if not contents:
            logger.warning("Skipping empty upload: %s", file_name)
            continue

        logger.info(
            "Extracting raw text from %s (%d/%d, %d bytes) for target=%s",
            file_name,
            index,
            len(files),
            len(contents),
            extraction_target,
        )
        try:
            extracted_text = extract_text_from_document(
                DocumentInput(
                    name=file_name,
                    content=contents,
                    content_type=upload.content_type,
                ),
                exam_name=exam_name,
                section_names=section_names,
                extraction_target=extraction_target,
            )
        except DocumentExtractionError as error:
            logger.error("Document extraction failed for %s: %s", file_name, error)
            raise HTTPException(status_code=502, detail=str(error)) from error

        extracted_documents.append((file_name, extracted_text))

    if not extracted_documents:
        raise HTTPException(status_code=422, detail="No text could be extracted from the uploaded files")

    return extracted_documents


@router.get("/health")
def healthcheck() -> dict[str, str]:
    logger.info("Health check requested")
    return {"status": "ok"}


@router.post("/api/ocr/extract-test", response_model=OCRExtractResponse)
async def extract_test_from_files(
    sections: str = Form(...),
    exam_name: str | None = Form(None),
    files: list[UploadFile] = File(...),
) -> OCRExtractResponse:
    started_at = perf_counter()
    parsed_sections = _parse_sections_payload(sections)

    logger.info(
        "OCR request started for exam='%s' with %d files and %d sections",
        exam_name or "",
        len(files),
        len(parsed_sections),
    )

    extracted_documents = await _extract_text_from_uploads(
        files,
        exam_name=exam_name,
        section_names=parsed_sections,
        extraction_target="test_result",
    )

    combined_text = combine_document_texts(extracted_documents)

    try:
        structured_result = structure_exam_document(
            exam_name=exam_name,
            sections=parsed_sections,
            extracted_text=combined_text,
        )
    except StructuringError as error:
        logger.error("Exam structuring failed: %s", error)
        raise HTTPException(status_code=502, detail=str(error)) from error

    elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "OCR request finished in %sms with %d extracted documents and %d warnings",
        elapsed_ms,
        len(extracted_documents),
        len(structured_result.warnings),
    )

    return OCRExtractResponse(
        exam_name=structured_result.exam_name or exam_name,
        test_date=structured_result.test_date,
        summary_sections=structured_result.summary_sections,
        result_sections=structured_result.result_sections,
        warnings=structured_result.warnings,
        extraction_quality=structured_result.extraction_quality,
        raw_text=combined_text,
        provider=get_settings().ocr_provider,
    )


@router.post("/api/ocr/extract-exam-from-text", response_model=ExamTemplateExtractResponse)
async def extract_exam_template_from_text(
    payload: ExamTemplateTextRequest,
) -> ExamTemplateExtractResponse:
    started_at = perf_counter()
    raw_text = payload.text.strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Text input is required")

    logger.info("Exam-template text extraction started with %d characters", len(raw_text))

    try:
        structured_result = structure_exam_template(raw_text, prefer_simple_parse=True)
    except StructuringError as error:
        logger.error("Exam-template structuring failed for text input: %s", error)
        raise HTTPException(status_code=502, detail=str(error)) from error

    elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "Exam-template text extraction finished in %sms with %d sections and %d warnings",
        elapsed_ms,
        len(structured_result.sections),
        len(structured_result.warnings),
    )

    return ExamTemplateExtractResponse(
        exam_name=structured_result.exam_name,
        sections=structured_result.sections,
        warnings=structured_result.warnings,
        extraction_quality=structured_result.extraction_quality,
        raw_text=raw_text,
        provider="text-parser",
    )


@router.post("/api/ocr/extract-exam-from-files", response_model=ExamTemplateExtractResponse)
async def extract_exam_template_from_files(
    files: list[UploadFile] = File(...),
) -> ExamTemplateExtractResponse:
    started_at = perf_counter()

    logger.info("Exam-template file extraction started with %d files", len(files))
    extracted_documents = await _extract_text_from_uploads(
        files,
        extraction_target="exam_template",
    )
    combined_text = combine_document_texts(extracted_documents)

    try:
        structured_result = structure_exam_template(combined_text)
    except StructuringError as error:
        logger.error("Exam-template structuring failed for uploaded files: %s", error)
        raise HTTPException(status_code=502, detail=str(error)) from error

    elapsed_ms = round((perf_counter() - started_at) * 1000, 2)
    logger.info(
        "Exam-template file extraction finished in %sms with %d sections and %d warnings",
        elapsed_ms,
        len(structured_result.sections),
        len(structured_result.warnings),
    )

    return ExamTemplateExtractResponse(
        exam_name=structured_result.exam_name,
        sections=structured_result.sections,
        warnings=structured_result.warnings,
        extraction_quality=structured_result.extraction_quality,
        raw_text=combined_text,
        provider=get_settings().ocr_provider,
    )
