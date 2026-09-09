"""Privacy-safe operational metrics for a voice interview."""

from dataclasses import dataclass

from loguru import logger
from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import (
    LLMUsageMetricsData,
    ProcessingMetricsData,
    SmartTurnMetricsData,
    STTUsageMetricsData,
    TTFAMetricsData,
    TTFATMetricsData,
    TTFBMetricsData,
    TTSUsageMetricsData,
    TextAggregationMetricsData,
    TurnMetricsData,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed


@dataclass(frozen=True, slots=True)
class VoiceMetric:
    name: str
    processor: str
    value: float
    unit: str


def safe_voice_metrics(metric) -> tuple[VoiceMetric, ...]:
    """Convert known Pipecat metrics without copying prompts or transcripts."""

    processor = metric.processor
    if isinstance(metric, TTFBMetricsData):
        return (VoiceMetric("time_to_first_byte", processor, metric.value * 1000, "ms"),)
    if isinstance(metric, TTFAMetricsData):
        return (VoiceMetric("time_to_first_audio", processor, metric.ttfa * 1000, "ms"),)
    if isinstance(metric, TTFATMetricsData):
        return (VoiceMetric("time_to_first_answer_token", processor, metric.ttfat * 1000, "ms"),)
    if isinstance(metric, ProcessingMetricsData):
        return (VoiceMetric("processing_time", processor, metric.value * 1000, "ms"),)
    if isinstance(metric, TextAggregationMetricsData):
        return (VoiceMetric("text_aggregation_time", processor, metric.value * 1000, "ms"),)
    if isinstance(metric, STTUsageMetricsData):
        return (VoiceMetric("stt_audio", processor, metric.value.audio_seconds, "seconds"),)
    if isinstance(metric, TTSUsageMetricsData):
        return (VoiceMetric("tts_text", processor, float(metric.value), "characters"),)
    if isinstance(metric, LLMUsageMetricsData):
        return (
            VoiceMetric("llm_prompt_tokens", processor, float(metric.value.prompt_tokens), "tokens"),
            VoiceMetric("llm_completion_tokens", processor, float(metric.value.completion_tokens), "tokens"),
        )
    if isinstance(metric, (SmartTurnMetricsData, TurnMetricsData)):
        return (
            VoiceMetric(
                "turn_detection_time", processor,
                float(metric.e2e_processing_time_ms), "ms",
            ),
        )
    return ()


class VoiceMetricsObserver(BaseObserver):
    """Capture each metrics frame once and emit metadata-only Loguru events."""

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.metrics: list[VoiceMetric] = []
        self._frames_seen: set[int] = set()

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame
        if not isinstance(frame, MetricsFrame) or frame.id in self._frames_seen:
            return
        self._frames_seen.add(frame.id)
        for raw_metric in frame.data:
            for metric in safe_voice_metrics(raw_metric):
                self.metrics.append(metric)
                logger.bind(
                    event="voice_metric",
                    session_id=self.session_id,
                    metric=metric.name,
                    processor=metric.processor,
                    value=round(metric.value, 3),
                    unit=metric.unit,
                ).info("Voice metric captured")
