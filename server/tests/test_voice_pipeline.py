import json
from pathlib import Path

import pytest
from pipecat.processors.frame_processor import FrameProcessor

from interviewflow.grounded_context import build_grounded_context
from interviewflow.interviewer import InterviewerSettings
from interviewflow.resume_ingestion import ResumeDocument, ResumePage
from interviewflow.rubric import load_approved_rubric
from interviewflow.voice_pipeline import (
    VoicePipelineError,
    _livekit_transport_params,
    build_voice_pipeline,
)
from interviewflow.voice_services import VoiceServices


class FakeTransport:
    def __init__(self):
        self.input_processor = FrameProcessor(name="browser_input")
        self.output_processor = FrameProcessor(name="browser_output")
        self.handlers = {}

    def input(self):
        return self.input_processor

    def output(self):
        return self.output_processor

    def event_handler(self, event_name):
        def register(handler):
            self.handlers[event_name] = handler
            return handler

        return register


@pytest.fixture
def grounded():
    data = json.loads((Path(__file__).parents[1] / "examples/interview.json").read_text())
    text = data["resume_text"]
    resume = ResumeDocument(
        "test", len(text.encode()), 1, (ResumePage(1, text),), text,
    )
    rubric = load_approved_rubric(data["rubric"], human_approved=True)
    return build_grounded_context(resume, data["job_description"], rubric)


def test_pipeline_uses_standard_order_and_enables_metrics(grounded):
    transport = FakeTransport()
    stt = FrameProcessor(name="stt")
    llm = FrameProcessor(name="llm")
    tts = FrameProcessor(name="tts")

    built = build_voice_pipeline(
        transport,
        grounded,
        InterviewerSettings("groq-key"),
        VoiceServices(stt=stt, tts=tts),
        llm=llm,
        session_id="test-session",
    )

    outer_processors = built.worker.pipeline.processors
    # Pipecat wraps our application pipeline and prepends RTVI automatically.
    assert outer_processors[1] is built.worker.rtvi
    application_processors = outer_processors[2].processors[1:-1]
    assert application_processors[0] is transport.input_processor
    assert application_processors[1] is stt
    assert application_processors[3] is llm
    assert application_processors[4] is tts
    assert application_processors[5] is transport.output_processor
    assert built.worker.params.enable_metrics is True
    assert built.worker.params.enable_usage_metrics is True
    assert built.worker.params.audio_in_sample_rate == 16000
    assert built.worker.params.audio_out_sample_rate == 24000
    assert built.controller.snapshot().remaining_seconds == 900
    assert built.controller.phase.value == "opening"
    assert set(transport.handlers) == {"on_client_connected", "on_client_disconnected"}

    user_aggregator = application_processors[2]
    assert user_aggregator._params.vad_analyzer is not None
    assert user_aggregator._params.vad_analyzer.params.stop_secs == 0.2
    assert user_aggregator._params.filter_incomplete_user_turns is False
    stop_strategies = user_aggregator._params.user_turn_strategies.stop
    assert len(stop_strategies) == 1
    assert type(stop_strategies[0]).__name__ == "SpeechTimeoutUserTurnStopStrategy"
    assert stop_strategies[0]._user_speech_timeout == 1.2
    assert not hasattr(built.lifecycle, "end_interview_tool")
    assert all(
        strategy._enable_interruptions
        for strategy in user_aggregator._user_turn_controller.user_turn_strategies.start
    )


def test_pipeline_rejects_oversized_context_before_provider_call(grounded):
    with pytest.raises(VoicePipelineError, match="context is too large"):
        build_voice_pipeline(
            FakeTransport(),
            grounded,
            InterviewerSettings("groq-key", max_context_bytes=10),
            VoiceServices(stt=FrameProcessor(), tts=FrameProcessor()),
            llm=FrameProcessor(),
        )


def test_livekit_transport_enables_two_way_audio():
    params = _livekit_transport_params()

    assert params.audio_in_enabled is True
    assert params.audio_out_enabled is True


def test_finalized_events_capture_transcript_without_synthetic_start(grounded):
    import asyncio
    from types import SimpleNamespace

    async def run():
        built = build_voice_pipeline(FakeTransport(), grounded, InterviewerSettings("fake"),
            VoiceServices(stt=FrameProcessor(), tts=FrameProcessor()), llm=FrameProcessor())
        processors = built.worker.pipeline.processors[2].processors[1:-1]
        user = processors[2]
        assert built.transcript.turns == ()
        await user._call_event_handler("on_user_turn_message_added",
            SimpleNamespace(content="My final answer", timestamp="2026-09-09T00:00:00Z"))
        await asyncio.sleep(0)
        await user._call_event_handler("on_user_turn_message_added",
            SimpleNamespace(content="with supporting detail", timestamp="2026-09-09T00:00:01Z"))
        await asyncio.sleep(0)
        assert len(built.transcript.turns) == 1
        assert built.transcript.turns[0].text == "My final answer with supporting detail"
        assert built.transcript.turns[0].role == "candidate"

    asyncio.run(run())
