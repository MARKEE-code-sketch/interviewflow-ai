from __future__ import annotations

import subprocess
import sys
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

SERVER_DIRECTORY = Path(__file__).resolve().parents[1]
SCRIPT = SERVER_DIRECTORY / "scripts" / "check_resume.py"


def _text_pdf() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=letter, pageCompression=0)
    document.drawString(72, 740, "Sample Candidate")
    document.drawString(72, 715, "Built and evaluated a grounded voice interview application")
    document.showPage()
    document.save()
    return output.getvalue()


def _run_checker(resume_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(resume_path)],
        cwd=SERVER_DIRECTORY,
        capture_output=True,
        check=False,
        encoding="utf-8",
        text=True,
    )


def test_checker_displays_extracted_resume_text(tmp_path: Path) -> None:
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(_text_pdf())

    completed = _run_checker(resume_path)

    assert completed.returncode == 0
    assert "Resume ingestion succeeded." in completed.stdout
    assert "Pages: 1" in completed.stdout
    assert "[Resume page 1]" in completed.stdout
    assert "grounded voice interview application" in completed.stdout


def test_checker_explains_an_unusable_resume(tmp_path: Path) -> None:
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    resume_path = tmp_path / "blank.pdf"
    resume_path.write_bytes(output.getvalue())

    completed = _run_checker(resume_path)

    assert completed.returncode == 1
    assert "Resume ingestion failed." in completed.stderr
    assert "Error code: insufficient_text" in completed.stderr
    assert "Scanned PDFs are not supported yet." in completed.stderr
