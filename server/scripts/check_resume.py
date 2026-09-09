"""Manually inspect the text extracted from a local resume PDF."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

# Direct script execution puts ``scripts`` on Python's import path. Add the
# server directory so this utility can import the adjacent application package.
SERVER_DIRECTORY = Path(__file__).resolve().parents[1]
if str(SERVER_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SERVER_DIRECTORY))

from interviewflow.resume_ingestion import (  # noqa: E402
    ResumeIngestionError,
    ingest_resume_pdf,
)


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a local resume PDF and display its extracted text."
    )
    parser.add_argument("resume", type=Path, help="Path to the resume PDF")
    args = parser.parse_args(arguments)

    try:
        pdf_bytes = args.resume.read_bytes()
    except OSError as error:
        print(
            f"Could not read the resume file ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 2

    try:
        resume = ingest_resume_pdf(pdf_bytes)
    except ResumeIngestionError as error:
        print("Resume ingestion failed.", file=sys.stderr)
        print(f"Error code: {error.code.value}", file=sys.stderr)
        print(f"Reason: {error}", file=sys.stderr)
        return 1

    print("Resume ingestion succeeded.")
    print(f"Pages: {resume.page_count}")
    print(f"Size: {resume.size_bytes} bytes")
    print("\nExtracted text:\n")
    print(resume.full_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
