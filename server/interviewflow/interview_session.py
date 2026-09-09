"""Text-session orchestrator built on Pipecat context and frame processing."""

import asyncio
import json
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from loguru import logger
from pipecat.frames.frames import LLMMessagesAppendFrame, LLMTextFrame, MetricsFrame
from pipecat.metrics.metrics import LLMUsageMetricsData
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.workers.runner import WorkerRunner

from interviewflow.grounded_context import GroundedContext
from interviewflow.interviewer import INTERVIEW_INSTRUCTIONS, InterviewerSettings, create_interviewer


class InterviewError(RuntimeError):
    """Safe error shown without provider response bodies or candidate text."""


@dataclass(frozen=True)
class InterviewReply:
    text: str
    first_text_ms: float
    total_ms: float


class _TextOutput(FrameProcessor):
    """A small terminal adapter; Pipecat handles the conversation itself."""

    def __init__(self, session):
        super().__init__()
        self.session = session

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame) and direction == FrameDirection.DOWNSTREAM:
            if frame.text and self.session._first_text_at is None:
                self.session._first_text_at = perf_counter()
            if self.session._on_text:
                self.session._on_text(frame.text)
        if isinstance(frame, MetricsFrame):
            for metric in frame.data:
                if isinstance(metric, LLMUsageMetricsData):
                    logger.bind(
                        event="interview_token_usage", session_id=self.session.session_id,
                        prompt_tokens=metric.value.prompt_tokens,
                        completion_tokens=metric.value.completion_tokens,
                    ).info("Interview token usage")
        await self.push_frame(frame, direction)


class InterviewSession:
    def __init__(self, grounded: GroundedContext, settings: InterviewerSettings, *, llm=None):
        self.settings = settings
        self.session_id = uuid4().hex
        # Fixed rules are configured on the LLM service; source JSON stays user data.
        self.context = LLMContext(grounded.to_messages()[1:])
        self.llm = llm if llm is not None else create_interviewer(settings)
        self._on_text = None
        self._first_text_at = None
        self._pending = None
        self._runner_task = None
        self._closed = False
        self._started = False
        user, assistant = LLMContextAggregatorPair(self.context)
        self.worker = PipelineWorker(
            Pipeline([user, self.llm, _TextOutput(self), assistant]),
            params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
            enable_rtvi=False, idle_timeout_secs=None,
        )
        self.runner = WorkerRunner(handle_sigint=False)

        @assistant.event_handler("on_assistant_turn_stopped")
        async def completed(aggregator, message):
            if self._pending is not None and not self._pending.done():
                if message.content.strip():
                    self._pending.set_result(message.content)
                else:
                    self._pending.set_exception(InterviewError("Groq returned no interview text."))

        @self.worker.event_handler("on_pipeline_error")
        async def failed(worker, frame):
            status = getattr(frame.exception, "status_code", None)
            reason = "Groq request failed. Check connectivity and model access."
            if status == 429:
                reason = "Groq rate limit reached. Wait before starting another session."
            elif status in (401, 403):
                reason = "Groq rejected access. Check the API key and model permissions."
            if self._pending is not None and not self._pending.done():
                self._pending.set_exception(InterviewError(reason))
            logger.bind(event="interview_provider_error", session_id=self.session_id,
                        status_code=status).warning("Interview provider error")

    async def start(self):
        if self._closed or self._started:
            raise InterviewError("This session cannot be started again.")
        self._started = True
        await self.runner.add_workers(self.worker)
        self._runner_task = asyncio.create_task(self.runner.run())

    async def reply(self, text: str, *, on_text=None) -> InterviewReply:
        if not self._started or self._closed:
            raise InterviewError("Start a new interview session first.")
        if self._pending is not None:
            raise InterviewError("Wait for the current response to finish.")
        if not text.strip():
            raise InterviewError("Please enter an answer.")
        messages = self.context.get_messages() + [{"role": "user", "content": text}]
        size = len((INTERVIEW_INSTRUCTIONS + json.dumps(messages, ensure_ascii=False)).encode("utf-8"))
        if size > self.settings.max_context_bytes:
            raise InterviewError("Interview context is too large. Shorten the documents or start a new session.")
        self._pending = asyncio.get_running_loop().create_future()
        self._on_text = on_text
        self._first_text_at = None
        started = perf_counter()
        try:
            await self.worker.queue_frame(LLMMessagesAppendFrame(
                messages=[{"role": "user", "content": text}], run_llm=True,
            ))
            result = await asyncio.wait_for(self._pending, self.settings.turn_timeout_seconds)
            ended = perf_counter()
            reply = InterviewReply(
                result, round(((self._first_text_at or ended) - started) * 1000, 1),
                round((ended - started) * 1000, 1),
            )
            logger.bind(event="interview_turn_completed", session_id=self.session_id,
                        first_text_ms=reply.first_text_ms, total_ms=reply.total_ms).info("Interview turn completed")
            return reply
        except TimeoutError:
            await self.close()
            raise InterviewError("Groq response timed out. Start a new session to retry.") from None
        except InterviewError:
            await self.close()
            raise
        finally:
            self._pending = None
            self._on_text = None

    async def close(self):
        if not self._closed:
            self._closed = True
            await self.worker.cancel()
            if self._runner_task is not None:
                await asyncio.wait_for(self._runner_task, 10)
