from __future__ import annotations

from io import BytesIO

import pytest
from loguru import logger
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from interviewflow.resume_ingestion import (
    MAX_PDF_BYTES,
    MAX_PDF_PAGES,
    ResumeIngestionError,
    ResumeIngestionErrorCode,
    ingest_resume_pdf,
)


def _text_pdf(*pages: tuple[str, ...]) -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=letter, pageCompression=0)
    for lines in pages:
        y = 740
        for line in lines:
            document.drawString(72, y, line)
            y -= 20
        document.showPage()
    document.save()
    return output.getvalue()


def _two_column_pdf() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=letter, pageCompression=0)
    document.drawString(72, 740, "Experience")
    document.drawString(72, 715, "Built retrieval evaluation pipelines")
    document.drawString(330, 740, "Skills")
    document.drawString(330, 715, "Python, Pipecat, DeepEval")
    document.showPage()
    document.save()
    return output.getvalue()


def _blank_pdf(page_count: int = 1) -> bytes:
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf() -> bytes:
    reader = PdfReader(BytesIO(_text_pdf(("Private resume content",))))
    output = BytesIO()
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("test-password")
    writer.write(output)
    return output.getvalue()


def _assert_error(data: bytes, expected: ResumeIngestionErrorCode, **kwargs: object) -> None:
    with pytest.raises(ResumeIngestionError) as raised:
        ingest_resume_pdf(data, **kwargs)
    assert raised.value.code is expected


def test_extracts_text_with_page_provenance() -> None:
    data = _text_pdf(
        ("Minal Sharma", "Python Engineer", "Built a voice AI application"),
        ("Experience", "Reduced API latency through profiling and caching"),
    )

    resume = ingest_resume_pdf(data)

    assert resume.page_count == 2
    assert resume.size_bytes == len(data)
    assert resume.pages[0].page_number == 1
    assert "Minal Sharma" in resume.pages[0].text
    assert resume.pages[1].page_number == 2
    assert "Reduced API latency" in resume.pages[1].text
    assert "[Resume page 1]" in resume.full_text
    assert "[Resume page 2]" in resume.full_text
    assert resume.document_id


def test_preserves_facts_from_a_two_column_resume() -> None:
    resume = ingest_resume_pdf(_two_column_pdf())

    assert "Built retrieval evaluation pipelines" in resume.full_text
    assert "Python, Pipecat, DeepEval" in resume.full_text


def test_rejects_an_invalid_content_type() -> None:
    _assert_error(
        _text_pdf(("A valid PDF with enough selectable text for this test",)),
        ResumeIngestionErrorCode.INVALID_FILE_TYPE,
        content_type="text/plain",
    )


def test_rejects_a_file_that_exceeds_the_size_limit() -> None:
    oversized = b"%PDF-1.7\n" + (b"x" * MAX_PDF_BYTES)
    _assert_error(oversized, ResumeIngestionErrorCode.FILE_TOO_LARGE)


def test_rejects_corrupt_pdf_bytes() -> None:
    _assert_error(b"%PDF-1.7\nthis is not a PDF", ResumeIngestionErrorCode.INVALID_PDF)


def test_rejects_an_encrypted_pdf() -> None:
    _assert_error(_encrypted_pdf(), ResumeIngestionErrorCode.ENCRYPTED_PDF)


def test_rejects_too_many_pages_before_extracting_text() -> None:
    _assert_error(
        _blank_pdf(MAX_PDF_PAGES + 1),
        ResumeIngestionErrorCode.TOO_MANY_PAGES,
    )


def test_rejects_a_pdf_without_usable_selectable_text() -> None:
    _assert_error(
        _blank_pdf(),
        ResumeIngestionErrorCode.INSUFFICIENT_TEXT,
    )


def test_logs_safe_metadata_without_resume_text() -> None:
    records: list[dict[str, object]] = []
    sink_id = logger.add(lambda message: records.append(message.record), level="INFO")
    private_text = "Candidate Secret Name and private@example.com"
    try:
        resume = ingest_resume_pdf(
            _text_pdf((private_text, "Built a sufficiently detailed Python application"))
        )
    finally:
        logger.remove(sink_id)

    ingestion_records = [
        record for record in records if record["extra"].get("document_id") == resume.document_id
    ]
    assert [record["extra"]["event"] for record in ingestion_records] == [
        "resume_ingestion_started",
        "resume_ingestion_completed",
    ]
    log_output = " ".join(
        f"{record['message']} {record['extra']}" for record in ingestion_records
    )
    assert private_text not in log_output
    assert "private@example.com" not in log_output
