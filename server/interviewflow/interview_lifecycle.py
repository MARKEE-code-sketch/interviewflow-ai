"""Connect interview timing decisions to supported Pipecat frames and events."""

import asyncio

from loguru import logger
from pipecat.frames.frames import (
    EndFrame,
    LLMMessagesAppendFrame,
    TTSSpeakFrame,
)

from interviewflow.interview_controller import InterviewController, InterviewPhase


CANDIDATE_QUESTIONS_INSTRUCTION = (
    "The timed interview has entered its final candidate-questions phase. "
    "Do not start another assessment question. Briefly invite the candidate to ask "
    "questions about the role or interview, then answer one question at a time using "
    "only the approved context."
)

CLOSING_MESSAGE = "Thank you for your time. The practice interview is now complete."


class InterviewLifecycle:
    """Apply controller transitions only when no conversational turn is active."""

    def __init__(
        self,
        controller: InterviewController,
        worker,
        *,
        monitor_interval_seconds: float = 1.0,
        client_sync_seconds: float = 5.0,
    ) -> None:
        self.controller = controller
        self._worker = worker
        self._monitor_interval_seconds = monitor_interval_seconds
        self._client_sync_seconds = client_sync_seconds
        self._waiting_for_user = False
        self._user_speaking = False
        self._assistant_speaking = False
        self._last_client_sync_elapsed = -client_sync_seconds
        self._monitor_task: asyncio.Task | None = None
        self._transition_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start timing and publish the first display snapshot."""

        self.controller.start()
        self._waiting_for_user = False
        await self._publish_timer(force=True)

    def start_monitor(self) -> None:
        """Run the lightweight timer inside Pipecat's managed task lifecycle."""

        if self._monitor_task is None:
            self._monitor_task = self._worker.create_task(
                self._monitor(), name="interview_timer"
            )

    def expect_assistant_response(self) -> None:
        self._waiting_for_user = False

    async def on_user_started(self) -> None:
        self._user_speaking = True
        self._waiting_for_user = False

    async def on_user_stopped(self) -> None:
        self._user_speaking = False
        self._waiting_for_user = False

    async def on_assistant_started(self) -> None:
        self._assistant_speaking = True

    async def on_assistant_stopped(self) -> None:
        self._assistant_speaking = False
        self._waiting_for_user = True
        if self.controller.complete_opening():
            await self._publish_timer(force=True)
        await self.tick()

    async def disconnect(self) -> None:
        self.controller.mark_ended()

    async def tick(self) -> None:
        """Publish timer state and apply a due transition at a safe boundary."""

        async with self._transition_lock:
            if self._is_safe_boundary():
                await self._apply_due_phase()
            await self._publish_timer()

    async def _apply_due_phase(self, *, force: bool = False) -> None:
        if not force and not self._is_safe_boundary():
            return

        due = self.controller.due_phase()
        if due == InterviewPhase.CANDIDATE_QUESTIONS:
            await self._worker.queue_frame(
                LLMMessagesAppendFrame(
                    messages=[
                        {"role": "developer", "content": CANDIDATE_QUESTIONS_INSTRUCTION}
                    ],
                    run_llm=True,
                )
            )
            self.controller.apply_phase(due)
            self.expect_assistant_response()
            await self._publish_timer(force=True)
            self._log_transition(due)
        elif due == InterviewPhase.CLOSING:
            await self._worker.queue_frames(
                [TTSSpeakFrame(CLOSING_MESSAGE), EndFrame(reason="interview_complete")]
            )
            self.controller.apply_phase(due)
            await self._publish_timer(force=True)
            self._log_transition(due)

    def _is_safe_boundary(self) -> bool:
        return (
            self._waiting_for_user
            and not self._user_speaking
            and not self._assistant_speaking
        )

    async def _publish_timer(self, *, force: bool = False) -> None:
        snapshot = self.controller.snapshot()
        if not force:
            elapsed_since_sync = snapshot.elapsed_seconds - self._last_client_sync_elapsed
            if elapsed_since_sync < self._client_sync_seconds:
                return
        try:
            await self._worker.rtvi.send_server_message(snapshot.to_client_message())
            self._last_client_sync_elapsed = snapshot.elapsed_seconds
        except Exception:
            logger.bind(event="interview_timer_client_sync_failed").warning(
                "Could not send interview timer status to client"
            )

    async def _monitor(self) -> None:
        while self.controller.phase not in {InterviewPhase.CLOSING, InterviewPhase.ENDED}:
            await asyncio.sleep(self._monitor_interval_seconds)
            await self.tick()

    @staticmethod
    def _log_transition(phase: InterviewPhase) -> None:
        logger.bind(event="interview_phase_changed", phase=phase.value).info(
            "Interview phase changed"
        )
