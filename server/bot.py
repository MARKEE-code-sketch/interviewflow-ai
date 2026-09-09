"""Local WebRTC entry point for the Module 4 voice interview smoke test."""

import json
import sys
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from interviewflow.logging_setup import configure_logging

configure_logging()

from interviewflow.grounded_context import build_grounded_context
from interviewflow.config import load_settings
from interviewflow.evaluator import EvaluationError, evaluate_interview, load_evaluator_settings
from loguru import logger
from interviewflow.interviewer import load_interviewer_settings
from interviewflow.resume_ingestion import ResumeDocument, ResumePage
from interviewflow.rubric import load_approved_rubric
from interviewflow.voice_pipeline import run_voice_interview
from interviewflow.voice_services import create_voice_services, load_voice_settings
from interviewflow.client_session import ClientSetupError, session_store
from interviewflow.persistence import PersistenceError


class SetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_base64: str = Field(min_length=1, max_length=7_500_000)
    job_description: str = Field(min_length=20, max_length=20_000)
    rubric: dict
    rubric_approved: bool


from pipecat.runner.run import app


@app.post("/api/interview-setup")
async def prepare_interview(request: SetupRequest):
    """Validate browser inputs before microphone access or provider calls."""

    try:
        prepared = session_store.prepare(
            resume_base64=request.resume_base64,
            job_description=request.job_description,
            rubric=request.rubric,
            rubric_approved=request.rubric_approved,
        )
    except ClientSetupError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return {
        "setup_id": prepared.setup_id,
        "page_count": prepared.page_count,
        "role_title": prepared.grounded.rubric.role_title,
        "criteria": [
            {"name": item.name, "weight": item.weight}
            for item in prepared.grounded.rubric.criteria
        ],
    }


@app.get("/api/interview-results/{session_id}")
async def interview_results(session_id: str):
    try:
        result = session_store.result(session_id)
    except PersistenceError:
        raise HTTPException(status_code=503, detail="Interview storage is unavailable.") from None
    if result is None:
        raise HTTPException(status_code=404, detail="Interview result not found.")
    return result


@app.get("/health")
async def health():
    """Process liveness check; it never calls an external AI provider."""

    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness includes the configured session database."""

    if not session_store.is_ready():
        raise HTTPException(status_code=503, detail="Interview storage is unavailable.")
    return {"status": "ready"}


EXAMPLE_INPUT = Path(__file__).resolve().parent / "examples" / "interview.json"


def load_example_context():
    """Load the reviewed fictional fixture; real uploads arrive in Module 7."""

    data = json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8"))
    text = data["resume_text"]
    resume = ResumeDocument(
        "fictional-demo",
        len(text.encode("utf-8")),
        1,
        (ResumePage(1, text),),
        text,
    )
    rubric = load_approved_rubric(data["rubric"], human_approved=True)
    return build_grounded_context(resume, data["job_description"], rubric)


async def bot(runner_args):
    setup_id = (getattr(runner_args, "body", None) or {}).get("setup_id")
    grounded = session_store.claim(setup_id).grounded if setup_id else load_example_context()
    session_id = getattr(runner_args, "session_id", None) or "local-session"
    session_store.mark_evaluating(session_id)
    app_settings = load_settings()
    interviewer_settings = load_interviewer_settings()
    voice_services = create_voice_services(load_voice_settings())
    transcript = await run_voice_interview(
        runner_args,
        grounded,
        interviewer_settings,
        voice_services,
        interview_duration_seconds=app_settings.interview_duration_minutes * 60,
    )
    if any(t.role == "candidate" and t.phase in {"opening", "main_interview"}
           for t in transcript.turns):
        try:
            scorecard = await evaluate_interview(
                grounded, transcript.turns, load_evaluator_settings()
            )
            session_store.save_scorecard(session_id, scorecard)
            return scorecard
        except EvaluationError as error:
            logger.bind(event="interview_scorecard_unavailable").warning(
                "Interview ended; scorecard unavailable"
            )
            session_store.mark_unavailable(session_id, str(error))
            return None
    session_store.mark_unavailable(
        session_id, "No completed candidate answers were available to score."
    )
    return None


if __name__ == "__main__":
    from pipecat.runner.run import main

    # Pipecat's development banner contains Unicode box-drawing characters.
    # Windows terminals may otherwise use cp1252 and fail before the server starts.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    main()
