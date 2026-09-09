import pytest

from evals.speech_quality import calculate_transcription_quality


def test_identical_transcript_has_zero_error():
    quality = calculate_transcription_quality(
        "I improved the API latency",
        "I improved the API latency",
    )
    assert quality.word_error_rate == 0
    assert quality.character_error_rate == 0


def test_transcript_error_is_measurable():
    quality = calculate_transcription_quality(
        "I improved API latency",
        "I improved latency",
    )
    assert quality.word_error_rate == pytest.approx(0.25)
    assert 0 < quality.character_error_rate < 1


def test_blank_reference_is_rejected():
    with pytest.raises(ValueError, match="must not be blank"):
        calculate_transcription_quality(" ", "anything")
