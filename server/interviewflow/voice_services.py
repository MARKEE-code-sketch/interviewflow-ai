"""Deepgram speech services used at the edge of the voice pipeline."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService

from interviewflow.config import DEFAULT_ENV_FILE


@dataclass(frozen=True, slots=True)
class VoiceSettings:
    """Validated English speech configuration; the API key is hidden in repr."""

    api_key: str = field(repr=False)
    stt_model: str = "nova-3-general"
    tts_voice: str = "aura-2-helena-en"

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("DEEPGRAM_API_KEY must be set")
        if not self.stt_model.strip():
            raise ValueError("DEEPGRAM_STT_MODEL must be set")
        if not self.tts_voice.strip():
            raise ValueError("DEEPGRAM_TTS_VOICE must be set")


@dataclass(frozen=True, slots=True)
class VoiceServices:
    """The two provider processors inserted into the Pipecat pipeline."""

    stt: DeepgramSTTService
    tts: DeepgramTTSService


def load_voice_settings(env_file: Path = DEFAULT_ENV_FILE) -> VoiceSettings:
    load_dotenv(env_file, override=False)
    return VoiceSettings(
        api_key=os.getenv("DEEPGRAM_API_KEY", ""),
        stt_model=os.getenv("DEEPGRAM_STT_MODEL", "nova-3-general"),
        tts_voice=os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-helena-en"),
    )


def create_voice_services(settings: VoiceSettings) -> VoiceServices:
    """Create streaming English STT and TTS using the supported Pipecat APIs."""

    stt = DeepgramSTTService(
        api_key=settings.api_key,
        settings=DeepgramSTTService.Settings(
            model=settings.stt_model,
            language="en",
            punctuate=True,
            smart_format=True,
        ),
    )
    tts = DeepgramTTSService(
        api_key=settings.api_key,
        settings=DeepgramTTSService.Settings(voice=settings.tts_voice),
    )
    return VoiceServices(stt=stt, tts=tts)
