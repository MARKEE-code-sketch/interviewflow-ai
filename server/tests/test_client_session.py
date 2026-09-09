import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from bot import app
from interviewflow.client_session import ClientSetupError, InterviewSessionStore


def _pdf_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "resume.pdf"
    document = canvas.Canvas(str(path))
    document.drawString(
        72,
        720,
        "Built and tested reliable Python APIs with PostgreSQL and measured latency.",
    )
    document.save()
    return path.read_bytes()


def _rubric() -> dict:
    return json.loads(
        (Path(__file__).parents[1] / "examples" / "interview.json").read_text()
    )["rubric"]


def test_browser_setup_is_one_time_and_keeps_no_pdf(tmp_path):
    store = InterviewSessionStore()
    prepared = store.prepare(
        resume_base64=base64.b64encode(_pdf_bytes(tmp_path)).decode("ascii"),
        job_description="Build reliable Python services and explain engineering trade-offs.",
        rubric=_rubric(),
        rubric_approved=True,
    )

    claimed = store.claim(prepared.setup_id)
    assert claimed.page_count == 1
    assert claimed.grounded.sources[0].source_id == "resume-page-1"
    assert not hasattr(claimed, "pdf_bytes")
    with pytest.raises(ClientSetupError, match="already used"):
        store.claim(prepared.setup_id)


@pytest.mark.parametrize(
    "resume,approved,message",
    [("not-base64", True, "could not be read"), ("", False, "approve the rubric")],
)
def test_browser_setup_returns_safe_errors(resume, approved, message):
    with pytest.raises(ClientSetupError, match=message):
        InterviewSessionStore().prepare(
            resume_base64=resume,
            job_description="A sufficiently detailed job description for testing.",
            rubric=_rubric(),
            rubric_approved=approved,
        )


def test_result_status_is_available_to_poll():
    store = InterviewSessionStore()
    store.mark_evaluating("session-1")
    assert store.result("session-1") == {"status": "evaluating"}
    store.save_scorecard("session-1", {"overall_score": 80})
    assert store.result("session-1")["scorecard"]["overall_score"] == 80


def test_setup_http_endpoint_returns_safe_session_metadata(tmp_path):
    response = TestClient(app).post(
        "/api/interview-setup",
        json={
            "resume_base64": base64.b64encode(_pdf_bytes(tmp_path)).decode("ascii"),
            "job_description": (
                "Build reliable Python APIs and explain engineering trade-offs."
            ),
            "rubric": _rubric(),
            "rubric_approved": True,
        },
    )

    assert response.status_code == 200
    assert len(response.json()["setup_id"]) == 32
    assert response.json()["page_count"] == 1
    assert "resume" not in response.text.lower()
