"""Validate a resume PDF and extract page-referenced text in memory."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from time import perf_counter
from uuid import uuid4

from loguru import logger
from pypdf import PdfReader

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_PAGE_CONTENT_BYTES = 20 * 1024 * 1024
MIN_EXTRACTED_CHARACTERS = 50


class ResumeIngestionErrorCode(str, Enum):
    """Stable error codes that an API or client can handle safely."""

    INVALID_FILE_TYPE = "invalid_file_type"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_PDF = "invalid_pdf"
    ENCRYPTED_PDF = "encrypted_pdf"
    TOO_MANY_PAGES = "too_many_pages"
    PAGE_CONTENT_TOO_LARGE = "page_content_too_large"
    TEXT_EXTRACTION_FAILED = "text_extraction_failed"
    INSUFFICIENT_TEXT = "insufficient_text"


_ERROR_MESSAGES = {
    ResumeIngestionErrorCode.INVALID_FILE_TYPE: "The uploaded file must be a PDF.",
    ResumeIngestionErrorCode.FILE_TOO_LARGE: "The PDF must be 5 MB or smaller.",
    ResumeIngestionErrorCode.INVALID_PDF: "The uploaded file is not a readable PDF.",
    ResumeIngestionErrorCode.ENCRYPTED_PDF: "Password-protected PDFs are not supported.",
    ResumeIngestionErrorCode.TOO_MANY_PAGES: "The PDF must contain no more than 10 pages.",
    ResumeIngestionErrorCode.PAGE_CONTENT_TOO_LARGE: "A PDF page is too complex to process safely.",
    ResumeIngestionErrorCode.TEXT_EXTRACTION_FAILED: "Text could not be extracted from the PDF.",
    ResumeIngestionErrorCode.INSUFFICIENT_TEXT: (
        "The PDF does not contain enough selectable text. Scanned PDFs are not supported yet."
    ),
}


class ResumeIngestionError(ValueError):
    """An expected, user-safe resume ingestion failure."""

    def __init__(
        self,
        code: ResumeIngestionErrorCode,
        document_id: str,
    ) -> None:
        self.code = code
        self.document_id = document_id
        super().__init__(_ERROR_MESSAGES[code])


@dataclass(frozen=True, slots=True)
class ResumePage:
    """Text extracted from one PDF page."""

    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class ResumeDocument:
    """Validated resume text with page-level provenance."""

    document_id: str
    size_bytes: int
    page_count: int
    pages: tuple[ResumePage, ...]
    full_text: str


def _normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace while keeping meaningful line breaks."""

    text = unicodedata.normalize("NFKC", text).replace("\x00", "").replace("\r", "\n")
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line).strip()


def _reject(
    code: ResumeIngestionErrorCode,
    document_id: str,
    started_at: float,
    **safe_metadata: object,
) -> None:
    logger.bind(
        event="resume_ingestion_rejected",
        document_id=document_id,
        error_code=code.value,
        elapsed_ms=round((perf_counter() - started_at) * 1000, 1),
        **safe_metadata,
    ).warning("Resume ingestion rejected")
    raise ResumeIngestionError(code, document_id)


def ingest_resume_pdf(
    pdf_bytes: bytes,
    *,
    content_type: str = "application/pdf",
) -> ResumeDocument:
    """Validate and extract one resume without saving the raw PDF to disk."""

    document_id = uuid4().hex
    size_bytes = len(pdf_bytes)
    started_at = perf_counter()

    logger.bind(
        event="resume_ingestion_started",
        document_id=document_id,
        size_bytes=size_bytes,
    ).info("Resume ingestion started")

    normalized_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type != "application/pdf":
        _reject(
            ResumeIngestionErrorCode.INVALID_FILE_TYPE,
            document_id,
            started_at,
            size_bytes=size_bytes,
        )

    if size_bytes > MAX_PDF_BYTES:
        _reject(
            ResumeIngestionErrorCode.FILE_TOO_LARGE,
            document_id,
            started_at,
            size_bytes=size_bytes,
        )

    if b"%PDF-" not in pdf_bytes[:1024]:
        _reject(
            ResumeIngestionErrorCode.INVALID_PDF,
            document_id,
            started_at,
            size_bytes=size_bytes,
        )

    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    except Exception as error:
        _reject(
            ResumeIngestionErrorCode.INVALID_PDF,
            document_id,
            started_at,
            size_bytes=size_bytes,
            exception_type=type(error).__name__,
        )

    if reader.is_encrypted:
        _reject(
            ResumeIngestionErrorCode.ENCRYPTED_PDF,
            document_id,
            started_at,
            size_bytes=size_bytes,
        )

    page_count = len(reader.pages)
    if page_count > MAX_PDF_PAGES:
        _reject(
            ResumeIngestionErrorCode.TOO_MANY_PAGES,
            document_id,
            started_at,
            size_bytes=size_bytes,
            page_count=page_count,
        )

    pages: list[ResumePage] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            content = page.get_contents()
            if content is None:
                raw_text = ""
            elif len(content.get_data()) > MAX_PAGE_CONTENT_BYTES:
                _reject(
                    ResumeIngestionErrorCode.PAGE_CONTENT_TOO_LARGE,
                    document_id,
                    started_at,
                    size_bytes=size_bytes,
                    page_count=page_count,
                    page_number=page_number,
                )
            else:
                raw_text = page.extract_text(
                    extraction_mode="layout",
                    layout_mode_space_vertically=False,
                )
        except ResumeIngestionError:
            raise
        except Exception as error:
            _reject(
                ResumeIngestionErrorCode.TEXT_EXTRACTION_FAILED,
                document_id,
                started_at,
                size_bytes=size_bytes,
                page_count=page_count,
                page_number=page_number,
                exception_type=type(error).__name__,
            )

        pages.append(ResumePage(page_number=page_number, text=_normalize_text(raw_text or "")))

    extracted_character_count = sum(
        character.isalnum() for page in pages for character in page.text
    )
    if extracted_character_count < MIN_EXTRACTED_CHARACTERS:
        _reject(
            ResumeIngestionErrorCode.INSUFFICIENT_TEXT,
            document_id,
            started_at,
            size_bytes=size_bytes,
            page_count=page_count,
            extracted_character_count=extracted_character_count,
        )

    full_text = "\n\n".join(
        f"[Resume page {page.page_number}]\n{page.text}" for page in pages if page.text
    )
    result = ResumeDocument(
        document_id=document_id,
        size_bytes=size_bytes,
        page_count=page_count,
        pages=tuple(pages),
        full_text=full_text,
    )

    logger.bind(
        event="resume_ingestion_completed",
        document_id=document_id,
        size_bytes=size_bytes,
        page_count=page_count,
        extracted_character_count=extracted_character_count,
        elapsed_ms=round((perf_counter() - started_at) * 1000, 1),
    ).info("Resume ingestion completed")

    return result
