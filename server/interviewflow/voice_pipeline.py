"""Compose and run the standard Pipecat cascaded voice pipeline."""

import json
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from interviewflow.grounded_context import GroundedContext
from interviewflow.interview_controller import InterviewController, InterviewTiming
from interviewflow.interview_lifecycle import InterviewLifecycle
from interviewflow.interviewer import INTERVIEW_INSTRUCTIONS, InterviewerSettings, create_interviewer
from interviewflow.voice_metrics import VoiceMetricsObserver
from interviewflow.voice_services import VoiceServices
from interviewflow.transcript import Transcript


class VoicePipelineError(RuntimeError):
    """Safe voice-pipeline error that does not include provider response data."""


def _livekit_transport_params():
    """Load LiveKit only when the hosted transport is selected."""

    from pipecat.transports.livekit.transport import LiveKitParams

    return LiveKitParams(audio_in_enabled=True, audio_out_enabled=True)


@dataclass(frozen=True, slots=True)
class VoicePipeline:
    worker: PipelineWorker
    metrics: VoiceMetricsObserver
    controller: InterviewController
    lifecycle: InterviewLifecycle
    transcript: Transcript


def _validate_context_size(grounded: GroundedContext, settings: InterviewerSettings) -> None:
    messages = grounded.to_messages()[1:]
    size = len((INTERVIEW_INSTRUCTIONS + json.dumps(messages, ensure_ascii=False)).encode("utf-8"))
    if size > settings.max_context_bytes:
        raise VoicePipelineError(
            "Interview context is too large. Shorten the documents before starting voice mode."
        )


def build_voice_pipeline(
    transport: BaseTransport,
    grounded: GroundedContext,
    interviewer_settings: InterviewerSettings,
    voice_services: VoiceServices,
    *,
    llm=None,
    session_id: str | None = None,
    interview_duration_seconds: float = 15 * 60,
    clock: Callable[[], float] | None = None,
) -> VoicePipeline:
    """Wire transport, speech services, context and LLM in Pipecat's normal order."""

    _validate_context_size(grounded, interviewer_settings)
    session_id = session_id or uuid4().hex
    transcript = Transcript()
    controller = InterviewController(
        InterviewTiming(total_seconds=interview_duration_seconds),
        **({"clock": clock} if clock is not None else {}),
    )
    context = LLMContext(grounded.to_messages()[1:])
    interviewer = llm if llm is not None else create_interviewer(interviewer_settings)
    user, assistant = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # Finalize after a short silence. The incomplete-turn LLM gate is
            # intentionally disabled: it can keep valid hosted turns open when
            # the interviewer prompt does not emit its private marker format.
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.6)),
        ),
    )
    pipeline = Pipeline([
        transport.input(),
        voice_services.stt,
        user,
        interviewer,
        voice_services.tts,
        transport.output(),
        assistant,
    ])
    metrics = VoiceMetricsObserver(session_id)
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[metrics],
        enable_rtvi=True,
        enable_turn_tracking=True,
        conversation_id=session_id,
    )
    lifecycle = InterviewLifecycle(controller, worker)
    greeting_started = False

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        nonlocal greeting_started
        if greeting_started:
            return
        greeting_started = True
        await lifecycle.start()
        lifecycle.start_monitor()
        lifecycle.expect_assistant_response()
        context.add_message({"role": "user", "content": "Please start the practice interview."})
        logger.bind(event="voice_client_ready", session_id=session_id).info("Voice client ready")
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.bind(event="voice_client_connected", session_id=session_id).info(
            "Voice client connected"
        )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.bind(event="voice_client_disconnected", session_id=session_id).info(
            "Voice client disconnected"
        )
        await lifecycle.disconnect()
        await worker.cancel()

    @user.event_handler("on_user_turn_started")
    async def on_user_turn_started(aggregator, strategy):
        await lifecycle.on_user_started()

    @user.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(aggregator, strategy, message):
        await lifecycle.on_user_stopped()

    @user.event_handler("on_user_turn_message_added")
    async def on_user_message(aggregator, message):
        transcript.append_candidate_fragment(
            message.content, controller.phase, timestamp=message.timestamp
        )

    @assistant.event_handler("on_assistant_turn_started")
    async def on_assistant_turn_started(aggregator):
        await lifecycle.on_assistant_started()

    @assistant.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message):
        transcript.append("interviewer", message.content, controller.phase,
                          timestamp=message.timestamp, interrupted=message.interrupted)
        await lifecycle.on_assistant_stopped()

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker, frame):
        status = getattr(frame.exception, "status_code", None)
        logger.bind(
            event="voice_pipeline_error",
            session_id=session_id,
            processor=type(frame.processor).__name__ if frame.processor else None,
            status_code=status,
        ).warning("Voice pipeline provider error")

    return VoicePipeline(
        worker=worker,
        metrics=metrics,
        controller=controller,
        lifecycle=lifecycle,
        transcript=transcript,
    )


async def run_voice_interview(
    runner_args: RunnerArguments,
    grounded: GroundedContext,
    interviewer_settings: InterviewerSettings,
    voice_services: VoiceServices,
    *,
    interview_duration_seconds: float = 15 * 60,
) -> Transcript:
    """Create the selected WebRTC transport and run one interview connection."""

    transport = await create_transport(
        runner_args,
        {
            "livekit": _livekit_transport_params,
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
            )
        },
    )
    built = build_voice_pipeline(
        transport,
        grounded,
        interviewer_settings,
        voice_services,
        session_id=runner_args.session_id,
        interview_duration_seconds=interview_duration_seconds,
    )
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(built.worker)
    await runner.run()
    return built.transcript
