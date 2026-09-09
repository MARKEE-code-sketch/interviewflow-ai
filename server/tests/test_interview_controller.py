import asyncio

import pytest
from pipecat.frames.frames import EndFrame, LLMMessagesAppendFrame, TTSSpeakFrame

from interviewflow.interview_controller import (
    InterviewController,
    InterviewPhase,
    InterviewTiming,
)
from interviewflow.interview_lifecycle import InterviewLifecycle


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeRTVI:
    def __init__(self) -> None:
        self.messages = []

    async def send_server_message(self, data) -> None:
        self.messages.append(data)


class FakeWorker:
    def __init__(self) -> None:
        self.rtvi = FakeRTVI()
        self.frames = []

    async def queue_frame(self, frame) -> None:
        self.frames.append(frame)

    async def queue_frames(self, frames) -> None:
        self.frames.extend(frames)


@pytest.mark.parametrize(
    "timing",
    [
        InterviewTiming(total_seconds=900, candidate_questions_seconds=120),
        InterviewTiming(total_seconds=60, candidate_questions_seconds=120),
    ],
)
def test_timer_snapshot_never_exposes_raw_monotonic_time(timing) -> None:
    clock = FakeClock()
    controller = InterviewController(timing, clock=clock)

    initial = controller.start().to_client_message()
    clock.now = 10.2
    later = controller.snapshot().to_client_message()

    assert initial["remaining_seconds"] == timing.total_seconds
    assert later["elapsed_seconds"] == 10
    assert "started_at" not in later
    assert "monotonic" not in later


def test_controller_reports_each_timed_phase_once() -> None:
    clock = FakeClock()
    controller = InterviewController(InterviewTiming(), clock=clock)
    controller.start()
    assert controller.complete_opening() is True
    assert controller.complete_opening() is False

    clock.now = 779.9
    assert controller.due_phase() is None
    clock.now = 780
    assert controller.due_phase() == InterviewPhase.CANDIDATE_QUESTIONS
    assert controller.apply_phase(InterviewPhase.CANDIDATE_QUESTIONS) is True
    assert controller.due_phase() is None

    clock.now = 900
    assert controller.due_phase() == InterviewPhase.CLOSING
    assert controller.apply_phase(InterviewPhase.CLOSING) is True
    assert controller.due_phase() is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"total_seconds": 0},
        {"total_seconds": float("inf")},
        {"candidate_questions_seconds": -1},
    ],
)
def test_invalid_timing_is_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        InterviewTiming(**kwargs)


def test_lifecycle_waits_for_a_safe_boundary_and_closes_once() -> None:
    async def run() -> None:
        clock = FakeClock()
        worker = FakeWorker()
        controller = InterviewController(InterviewTiming(), clock=clock)
        lifecycle = InterviewLifecycle(controller, worker)

        await lifecycle.start()
        await lifecycle.on_assistant_stopped()
        assert controller.phase == InterviewPhase.MAIN_INTERVIEW

        clock.now = 780
        await lifecycle.on_user_started()
        await lifecycle.tick()
        assert not worker.frames

        await lifecycle.on_user_stopped()
        await lifecycle.tick()
        assert not worker.frames

        await lifecycle.on_assistant_started()
        await lifecycle.on_assistant_stopped()
        assert controller.phase == InterviewPhase.CANDIDATE_QUESTIONS
        assert len(worker.frames) == 1
        assert isinstance(worker.frames[0], LLMMessagesAppendFrame)
        assert worker.frames[0].run_llm is True

        await lifecycle.on_assistant_started()
        await lifecycle.on_assistant_stopped()
        clock.now = 900
        await lifecycle.tick()

        assert controller.phase == InterviewPhase.CLOSING
        assert isinstance(worker.frames[-2], TTSSpeakFrame)
        assert isinstance(worker.frames[-1], EndFrame)
        frame_count = len(worker.frames)
        await lifecycle.tick()
        assert len(worker.frames) == frame_count
        assert worker.rtvi.messages[-1]["phase"] == "closing"

    asyncio.run(run())


def test_only_elapsed_time_can_make_closing_due() -> None:
    clock = FakeClock()
    controller = InterviewController(InterviewTiming(), clock=clock)
    controller.start()
    controller.complete_opening()

    clock.now = 899
    assert controller.due_phase() == InterviewPhase.CANDIDATE_QUESTIONS
    controller.apply_phase(InterviewPhase.CANDIDATE_QUESTIONS)
    assert controller.due_phase() is None

    clock.now = 900
    assert controller.due_phase() == InterviewPhase.CLOSING
