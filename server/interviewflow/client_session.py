"""Prepare browser-supplied interview inputs and expose session results in memory."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from threading import Lock
from uuid import uuid4

from loguru import logger

from interviewflow.grounded_context import GroundedContext, build_grounded_context
from interviewflow.resume_ingestion import ResumeIngestionError, ingest_resume_pdf
from interviewflow.rubric import load_approved_rubric


class ClientSetupError(ValueError):
    """A safe input error that can be shown in the browser."""


@dataclass(frozen=True, slots=True)
class PreparedInterview:
    setup_id: str
    grounded: GroundedContext
    page_count: int


class InterviewSessionStore:
    """Small process-local handoff between HTTP setup, the bot, and result polling."""

    def __init__(self) -> None:
        self._setups: dict[str, PreparedInterview] = {}
        self._results: dict[str, dict] = {}
        self._lock = Lock()

    def prepare(
        self,
        *,
        resume_base64: str,
        job_description: str,
        rubric: dict,
        rubric_approved: bool,
    ) -> PreparedInterview:
        if rubric_approved is not True:
            raise ClientSetupError("Review and approve the rubric before starting.")
        try:
            pdf_bytes = base64.b64decode(resume_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ClientSetupError("The uploaded resume could not be read.") from None

        try:
            resume = ingest_resume_pdf(pdf_bytes)
            approved_rubric = load_approved_rubric(rubric, human_approved=True)
            grounded = build_grounded_context(resume, job_description, approved_rubric)
        except ResumeIngestionError as error:
            raise ClientSetupError(str(error)) from None
        except ValueError as error:
            raise ClientSetupError(str(error)) from None

        prepared = PreparedInterview(uuid4().hex, grounded, resume.page_count)
        with self._lock:
            self._setups[prepared.setup_id] = prepared
        logger.bind(
            event="client_interview_prepared",
            setup_id=prepared.setup_id,
            resume_page_count=prepared.page_count,
            rubric_id=approved_rubric.rubric_id,
        ).info("Browser interview inputs prepared")
        return prepared

    def claim(self, setup_id: str) -> PreparedInterview:
        with self._lock:
            prepared = self._setups.pop(setup_id, None)
        if prepared is None:
            raise ClientSetupError("This interview setup is missing or was already used.")
        return prepared

    def mark_evaluating(self, session_id: str) -> None:
        with self._lock:
            self._results[session_id] = {"status": "evaluating"}

    def save_scorecard(self, session_id: str, scorecard) -> None:
        payload = scorecard.model_dump(mode="json") if hasattr(scorecard, "model_dump") else scorecard
        with self._lock:
            self._results[session_id] = {"status": "complete", "scorecard": payload}

    def mark_unavailable(self, session_id: str, reason: str) -> None:
        with self._lock:
            self._results[session_id] = {"status": "unavailable", "message": reason}

    def result(self, session_id: str) -> dict | None:
        with self._lock:
            value = self._results.get(session_id)
            return dict(value) if value is not None else None


session_store = InterviewSessionStore()
