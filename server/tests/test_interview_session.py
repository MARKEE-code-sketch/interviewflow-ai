import asyncio
import json
from pathlib import Path

import pytest
from pipecat.frames.frames import (
    LLMContextFrame, LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame,
)
from pipecat.processors.frame_processor import FrameProcessor

from interviewflow.grounded_context import build_grounded_context
from interviewflow.interview_session import InterviewError, InterviewSession
from interviewflow.interviewer import InterviewerSettings
from interviewflow.resume_ingestion import ResumeDocument, ResumePage
from interviewflow.rubric import load_approved_rubric


@pytest.fixture
def grounded():
    data = json.loads((Path(__file__).parents[1] / "examples/interview.json").read_text())
    resume = ResumeDocument("test", 100, 1, (ResumePage(1, data["resume_text"]),), "")
    return build_grounded_context(resume, data["job_description"],
                                  load_approved_rubric(data["rubric"], human_approved=True))


class FakeInterviewer(FrameProcessor):
    def __init__(self, mode="normal"):
        super().__init__()
        self.mode = mode
        self.calls = []

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return
        self.calls.append(list(frame.context.get_messages()))
        if self.mode == "timeout":
            await asyncio.sleep(10)
            return
        await self.push_frame(LLMFullResponseStartFrame())
        if self.mode == "error":
            await self.push_error(error_msg="PRIVATE PROVIDER BODY")
        elif self.mode == "rate_limit":
            error = RuntimeError("PRIVATE PROVIDER BODY")
            error.status_code = 429
            await self.push_error(error_msg="PRIVATE PROVIDER BODY", exception=error)
        elif self.mode != "empty":
            await self.push_frame(LLMTextFrame("What did "))
            await self.push_frame(LLMTextFrame("you measure?"))
        await self.push_frame(LLMFullResponseEndFrame())


def test_real_pipecat_pipeline_retains_history_and_streams(grounded):
    async def run():
        fake = FakeInterviewer()
        session = InterviewSession(grounded, InterviewerSettings("fake"), llm=fake)
        chunks = []
        try:
            await session.start()
            result = await session.reply("I used MongoDB", on_text=chunks.append)
            assert result.text == "What did you measure?"
            assert "".join(chunks) == result.text
            assert 0 <= result.first_text_ms <= result.total_ms
            await session.reply("Correction: PostgreSQL")
            history = fake.calls[-1]
            assert history[-1] == {"role": "user", "content": "Correction: PostgreSQL"}
            assert any(m.get("role") == "assistant" and m.get("content") == result.text for m in history)
            assert any(m.get("content") == "I used MongoDB" for m in history)
        finally:
            await session.close()
        assert session._runner_task.done()
    asyncio.run(run())


@pytest.mark.parametrize("mode,expected", [
    ("timeout", "timed out"), ("error", "request failed"), ("empty", "no interview text"),
    ("rate_limit", "rate limit"),
])
def test_failed_turn_closes_cleanly(grounded, mode, expected):
    async def run():
        session = InterviewSession(grounded, InterviewerSettings("fake", turn_timeout_seconds=1),
                                   llm=FakeInterviewer(mode))
        try:
            await session.start()
            with pytest.raises(InterviewError, match=expected) as error:
                await session.reply("Candidate answer")
            assert "PRIVATE" not in str(error.value)
            assert session._closed
        finally:
            await session.close()
    asyncio.run(run())


def test_context_budget_rejects_without_call_or_truncation(grounded):
    async def run():
        fake = FakeInterviewer()
        session = InterviewSession(grounded, InterviewerSettings("fake", max_context_bytes=10), llm=fake)
        try:
            await session.start()
            original = list(session.context.get_messages())
            with pytest.raises(InterviewError, match="too large"):
                await session.reply("Answer")
            assert session.context.get_messages() == original
            assert not fake.calls
        finally:
            await session.close()
    asyncio.run(run())


def test_api_key_is_excluded_from_settings_repr():
    assert "PRIVATE-KEY" not in repr(InterviewerSettings("PRIVATE-KEY"))
    with pytest.raises(ValueError):
        InterviewerSettings("")
