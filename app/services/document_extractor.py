import base64
import logging
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import requests
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.core.config import get_settings
from app.prompts.document_extraction import build_exam_document_extraction_prompt
from app.prompts.exam_template_extraction import build_exam_template_document_extraction_prompt
from app.utils.text import strip_markdown_fences, strip_non_bmp_characters


logger = logging.getLogger("examtracker.ocr")


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


@dataclass
class DocumentInput:
    name: str
    content: bytes
    content_type: str | None = None


class DocumentExtractionError(RuntimeError):
    pass


def _build_extraction_prompt(
    extraction_target: str,
    exam_name: str | None,
    section_names: list[str],
) -> str:
    if extraction_target == "exam_template":
        return build_exam_template_document_extraction_prompt()

    return build_exam_document_extraction_prompt(exam_name, section_names)


def get_file_mime_type(file_name: str, content_type: str | None = None) -> str:
    if content_type:
        return content_type

    extension = Path(file_name).suffix.lower()
    if extension == ".pdf":
        return "application/pdf"
    if extension in {".png"}:
        return "image/png"
    if extension in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if extension == ".webp":
        return "image/webp"

    return "application/octet-stream"


def is_pdf_document(file_name: str, content_type: str | None = None) -> bool:
    mime_type = get_file_mime_type(file_name, content_type)
    return mime_type == "application/pdf" or file_name.lower().endswith(".pdf")


def render_pdf_pages_as_images(document: DocumentInput) -> list[DocumentInput]:
    logger.info("Rendering PDF into page images: %s", document.name)
    pdf_document = pymupdf.open(stream=document.content, filetype="pdf")
    rendered_pages: list[DocumentInput] = []

    for page_index in range(pdf_document.page_count):
        page = pdf_document[page_index]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        page_bytes = pixmap.tobytes("png")
        rendered_pages.append(
            DocumentInput(
                name=f"{Path(document.name).stem}-page-{page_index + 1}.png",
                content=page_bytes,
                content_type="image/png",
            )
        )

    logger.info("Rendered %d PDF pages for %s", len(rendered_pages), document.name)
    return rendered_pages


def _require_openai_settings() -> tuple[str, str, int]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise DocumentExtractionError("OPENAI_API_KEY is missing for OCR extraction.")

    return (
        settings.openai_api_key,
        settings.openai_extraction_model,
        settings.request_timeout_seconds,
    )


def _extract_text_from_openai_response(result: dict) -> str:
    for output_item in result.get("output", []):
        for content_item in output_item.get("content", []):
            text = content_item.get("text")
            if text:
                return strip_non_bmp_characters(strip_markdown_fences(text))

    for choice in result.get("choices", []):
        message = choice.get("message", {})
        text = message.get("content")
        if text:
            return strip_non_bmp_characters(strip_markdown_fences(text))

    return ""


def _extract_text_from_langchain_message_content(content: object) -> str:
    if isinstance(content, str):
        return strip_non_bmp_characters(strip_markdown_fences(content))

    if isinstance(content, list):
        text_chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    text_chunks.append(str(text))

        return strip_non_bmp_characters(strip_markdown_fences("\n".join(text_chunks)))

    return ""


def extract_text_from_pdf_with_openai(document: DocumentInput) -> str:
    return _extract_text_from_pdf_with_openai(document, exam_name=None, section_names=None)


def _extract_text_from_pdf_with_openai(
    document: DocumentInput,
    exam_name: str | None,
    section_names: list[str] | None,
    extraction_target: str = "test_result",
) -> str:
    api_key, model, timeout_seconds = _require_openai_settings()
    mime_type = get_file_mime_type(document.name, document.content_type)
    base64_content = base64.b64encode(document.content).decode("utf-8")
    extraction_prompt = _build_extraction_prompt(
        extraction_target,
        exam_name,
        section_names or [],
    )

    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": document.name,
                        "file_data": f"data:{mime_type};base64,{base64_content}",
                    },
                    {
                        "type": "input_text",
                        "text": extraction_prompt,
                    },
                ],
            }
        ],
    }

    logger.info("Extracting text from PDF via OpenAI Responses API: %s", document.name)
    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        timeout=timeout_seconds,
    )

    if response.status_code != 200:
        logger.error("OpenAI PDF extraction failed: %s", response.text)
        raise DocumentExtractionError(
            f"OpenAI PDF extraction failed with status {response.status_code}."
        )

    extracted_text = _extract_text_from_openai_response(response.json())
    if not extracted_text:
        raise DocumentExtractionError(f"No extracted text returned for PDF '{document.name}'.")

    return extracted_text


def extract_text_from_image_with_openai(document: DocumentInput) -> str:
    return _extract_text_from_image_with_openai(document, exam_name=None, section_names=None)


def _extract_text_from_image_with_openai(
    document: DocumentInput,
    exam_name: str | None,
    section_names: list[str] | None,
    extraction_target: str = "test_result",
) -> str:
    api_key, model, timeout_seconds = _require_openai_settings()
    mime_type = get_file_mime_type(document.name, document.content_type)
    base64_content = base64.b64encode(document.content).decode("utf-8")
    extraction_prompt = _build_extraction_prompt(
        extraction_target,
        exam_name,
        section_names or [],
    )

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": extraction_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_content}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
    }

    logger.info("Extracting text from image via OpenAI Chat Completions API: %s", document.name)
    response = requests.post(
        OPENAI_CHAT_COMPLETIONS_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json=payload,
        timeout=timeout_seconds,
    )

    if response.status_code != 200:
        logger.error("OpenAI image extraction failed: %s", response.text)
        raise DocumentExtractionError(
            f"OpenAI image extraction failed with status {response.status_code}."
        )

    extracted_text = _extract_text_from_openai_response(response.json())
    if not extracted_text:
        raise DocumentExtractionError(f"No extracted text returned for image '{document.name}'.")

    return extracted_text


def extract_text_from_image_with_groq(document: DocumentInput) -> str:
    return _extract_text_from_image_with_groq(document, exam_name=None, section_names=None)


def _extract_text_from_image_with_groq(
    document: DocumentInput,
    exam_name: str | None,
    section_names: list[str] | None,
    extraction_target: str = "test_result",
) -> str:
    settings = get_settings()
    if not settings.groq_api_key:
        raise DocumentExtractionError("GROQ_API_KEY is missing for OCR extraction.")

    mime_type = get_file_mime_type(document.name, document.content_type)
    base64_content = base64.b64encode(document.content).decode("utf-8")
    extraction_prompt = _build_extraction_prompt(
        extraction_target,
        exam_name,
        section_names or [],
    )

    logger.info("Extracting text from image via Groq vision: %s", document.name)
    llm = ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_extraction_model,
        temperature=0,
        timeout=settings.request_timeout_seconds,
    )
    response = llm.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": extraction_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_content}",
                        },
                    },
                ]
            )
        ]
    )

    extracted_text = _extract_text_from_langchain_message_content(response.content)
    if not extracted_text:
        raise DocumentExtractionError(f"No extracted text returned for image '{document.name}'.")

    return extracted_text


def extract_text_from_document(
    document: DocumentInput,
    exam_name: str | None = None,
    section_names: list[str] | None = None,
    extraction_target: str = "test_result",
) -> str:
    settings = get_settings()

    if is_pdf_document(document.name, document.content_type):
        try:
            page_documents = render_pdf_pages_as_images(document)
        except Exception as error:
            logger.warning(
                "PDF page rendering failed for %s, falling back to OpenAI file extraction: %s",
                document.name,
                error,
            )
            return _extract_text_from_pdf_with_openai(
                document,
                exam_name,
                section_names,
                extraction_target=extraction_target,
            )

        extracted_page_texts: list[tuple[str, str]] = []
        for page_document in page_documents:
            if settings.ocr_provider == "groq":
                page_text = _extract_text_from_image_with_groq(
                    page_document,
                    exam_name,
                    section_names,
                    extraction_target=extraction_target,
                )
            elif settings.ocr_provider == "openai":
                page_text = _extract_text_from_image_with_openai(
                    page_document,
                    exam_name,
                    section_names,
                    extraction_target=extraction_target,
                )
            else:
                raise DocumentExtractionError(
                    f"OCR provider '{settings.ocr_provider}' is not implemented. Use 'groq' or 'openai'."
                )

            extracted_page_texts.append((page_document.name, page_text))

        return combine_document_texts(extracted_page_texts)

    if settings.ocr_provider == "groq":
        return _extract_text_from_image_with_groq(
            document,
            exam_name,
            section_names,
            extraction_target=extraction_target,
        )

    if settings.ocr_provider == "openai":
        return _extract_text_from_image_with_openai(
            document,
            exam_name,
            section_names,
            extraction_target=extraction_target,
        )

    raise DocumentExtractionError(
        f"OCR provider '{settings.ocr_provider}' is not implemented. Use 'groq' or 'openai'."
    )


def combine_document_texts(extracted_documents: list[tuple[str, str]]) -> str:
    chunks: list[str] = []
    for file_name, extracted_text in extracted_documents:
        chunks.append(
            f"--- BEGIN DOCUMENT: {strip_non_bmp_characters(file_name)} ---\n"
            f"{strip_non_bmp_characters(extracted_text)}\n"
            f"--- END DOCUMENT: {strip_non_bmp_characters(file_name)} ---"
        )

    return "\n\n".join(chunks)
