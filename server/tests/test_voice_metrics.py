import asyncio

from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import (
    LLMTokenUsage,
    LLMUsageMetricsData,
    STTUsage,
    STTUsageMetricsData,
    TTFAMetricsData,
    TTFBMetricsData,
    TTSUsageMetricsData,
)
from pipecat.observers.base_observer import FramePushed
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from interviewflow.voice_metrics import VoiceMetricsObserver, safe_voice_metrics


def test_safe_voice_metrics_converts_latency_and_usage_without_text():
    raw = [
        TTFBMetricsData(processor="Groq", model="model", value=0.25),
        TTFAMetricsData(
            processor="DeepgramTTS", model="voice", ttfa=0.4,
            ttfb=0.3, leading_silence=0.1,
        ),
        STTUsageMetricsData(
            processor="DeepgramSTT", model="stt", value=STTUsage(audio_seconds=2.5),
        ),
        TTSUsageMetricsData(processor="DeepgramTTS", model="voice", value=42),
        LLMUsageMetricsData(
            processor="Groq",
            model="model",
            value=LLMTokenUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
        ),
    ]

    metrics = [item for source in raw for item in safe_voice_metrics(source)]

    assert [(item.name, item.value, item.unit) for item in metrics] == [
        ("time_to_first_byte", 250.0, "ms"),
        ("time_to_first_audio", 400.0, "ms"),
        ("stt_audio", 2.5, "seconds"),
        ("tts_text", 42.0, "characters"),
        ("llm_prompt_tokens", 10.0, "tokens"),
        ("llm_completion_tokens", 4.0, "tokens"),
    ]
    assert "candidate answer" not in repr(metrics).lower()


def test_metrics_observer_records_each_frame_once():
    async def run():
        observer = VoiceMetricsObserver("session")
        frame = MetricsFrame(
            data=[TTFBMetricsData(processor="Groq", model="model", value=0.1)]
        )
        processor = FrameProcessor()
        pushed = FramePushed(
            source=processor,
            destination=processor,
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
            timestamp=1,
        )

        await observer.on_push_frame(pushed)
        await observer.on_push_frame(pushed)

        assert len(observer.metrics) == 1
        assert observer.metrics[0].value == 100.0

    asyncio.run(run())
