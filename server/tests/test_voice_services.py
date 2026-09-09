from pathlib import Path

import pytest

from interviewflow import voice_services
from interviewflow.voice_services import VoiceSettings, create_voice_services, load_voice_settings


class FakeSTT:
    class Settings:
        def __init__(self, **values):
            self.values = values

    def __init__(self, **values):
        self.values = values


class FakeTTS:
    class Settings:
        def __init__(self, **values):
            self.values = values

    def __init__(self, **values):
        self.values = values


def test_voice_settings_load_from_env_without_exposing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPGRAM_STT_MODEL", raising=False)
    monkeypatch.delenv("DEEPGRAM_TTS_VOICE", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPGRAM_API_KEY=PRIVATE-KEY\n"
        "DEEPGRAM_STT_MODEL=custom-stt\n"
        "DEEPGRAM_TTS_VOICE=custom-voice\n",
        encoding="utf-8",
    )

    settings = load_voice_settings(Path(env_file))

    assert settings.api_key == "PRIVATE-KEY"
    assert settings.stt_model == "custom-stt"
    assert settings.tts_voice == "custom-voice"
    assert "PRIVATE-KEY" not in repr(settings)


@pytest.mark.parametrize(
    "settings",
    [VoiceSettings("key", "model", "voice")],
)
def test_create_voice_services_uses_streaming_english_configuration(monkeypatch, settings):
    monkeypatch.setattr(voice_services, "DeepgramSTTService", FakeSTT)
    monkeypatch.setattr(voice_services, "DeepgramTTSService", FakeTTS)

    services = create_voice_services(settings)

    assert services.stt.values["api_key"] == "key"
    assert services.stt.values["settings"].values == {
        "model": "model",
        "language": "en",
        "punctuate": True,
        "smart_format": True,
    }
    assert services.tts.values["api_key"] == "key"
    assert services.tts.values["settings"].values == {"voice": "voice"}


@pytest.mark.parametrize(
    "values",
    [("", "model", "voice"), ("key", "", "voice"), ("key", "model", "")],
)
def test_voice_settings_reject_missing_values(values):
    with pytest.raises(ValueError):
        VoiceSettings(*values)
