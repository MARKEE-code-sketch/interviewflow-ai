"""Prepare browser inputs and hand session state to the voice worker."""

from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass
from time import time
from typing import Callable
from uuid import uuid4

from loguru import logger

from interviewflow.grounded_context import (
    ContextSource,
    GroundedContext,
    build_grounded_context,
)
from interviewflow.persistence import (
    MemoryPersistence,
    PersistenceError,
    SessionPersistence,
    create_session_persistence,
)
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
    """One-use setup handoff and expiring result storage."""

    def __init__(
        self,
        persistence: SessionPersistence | None = None,
        *,
        clock: Callable[[], float] = time,
        setup_ttl_seconds: float = 60 * 60,
        result_ttl_seconds: float = 7 * 24 * 60 * 60,
    ) -> None:
        self._persistence = persistence or MemoryPersistence()
        self._clock = clock
        self._setup_ttl_seconds = setup_ttl_seconds
        self._result_ttl_seconds = result_ttl_seconds

    @staticmethod
    def _to_payload(prepared: PreparedInterview) -> dict:
        return {
            "setup_id": prepared.setup_id,
            "page_count": prepared.page_count,
            "rubric": prepared.grounded.rubric.to_dict(),
            "sources": [asdict(source) for source in prepared.grounded.sources],
        }

    @staticmethod
    def _from_payload(payload: dict) -> PreparedInterview:
        try:
            rubric = load_approved_rubric(payload["rubric"], human_approved=True)
            grounded = GroundedContext(
                rubric=rubric,
                sources=tuple(ContextSource(**source) for source in payload["sources"]),
            )
            return PreparedInterview(payload["setup_id"], grounded, payload["page_count"])
        except (KeyError, TypeError, ValueError) as error:
            raise ClientSetupError("This interview setup could not be restored.") from error

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
        try:
            self._persistence.save_setup(
                prepared.setup_id,
                self._to_payload(prepared),
                self._clock() + self._setup_ttl_seconds,
            )
        except PersistenceError as error:
            logger.bind(event="interview_storage_write_failed", error_code=str(error)).warning(
                "Interview setup storage failed"
            )
            raise ClientSetupError("Interview storage is temporarily unavailable.") from None
        logger.bind(
            event="client_interview_prepared",
            setup_id=prepared.setup_id,
            resume_page_count=prepared.page_count,
            rubric_id=approved_rubric.rubric_id,
        ).info("Browser interview inputs prepared")
        return prepared

    def claim(self, setup_id: str) -> PreparedInterview:
        try:
            payload = self._persistence.claim_setup(setup_id, self._clock())
        except PersistenceError as error:
            logger.bind(event="interview_storage_read_failed", error_code=str(error)).warning(
                "Interview setup storage failed"
            )
            raise ClientSetupError("Interview storage is temporarily unavailable.") from None
        if payload is None:
            raise ClientSetupError("This interview setup is missing or was already used.")
        return self._from_payload(payload)

    def mark_evaluating(self, session_id: str) -> None:
        self._save_result(session_id, {"status": "evaluating"})

    def save_scorecard(self, session_id: str, scorecard) -> None:
        payload = (
            scorecard.model_dump(mode="json")
            if hasattr(scorecard, "model_dump")
            else scorecard
        )
        self._save_result(session_id, {"status": "complete", "scorecard": payload})

    def mark_unavailable(self, session_id: str, reason: str) -> None:
        self._save_result(session_id, {"status": "unavailable", "message": reason})

    def _save_result(self, session_id: str, payload: dict) -> None:
        self._persistence.save_result(
            session_id, payload, self._clock() + self._result_ttl_seconds
        )

    def result(self, session_id: str) -> dict | None:
        value = self._persistence.get_result(session_id, self._clock())
        return dict(value) if value is not None else None

    def is_ready(self) -> bool:
        return self._persistence.healthcheck()


session_store = InterviewSessionStore(create_session_persistence())
