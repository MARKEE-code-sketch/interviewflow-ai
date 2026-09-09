"""Word and character error rates for STT evaluation only."""

from dataclasses import dataclass

from jiwer import cer, wer


@dataclass(frozen=True, slots=True)
class TranscriptionQuality:
    word_error_rate: float
    character_error_rate: float


def calculate_transcription_quality(reference: str, hypothesis: str) -> TranscriptionQuality:
    if not reference.strip():
        raise ValueError("Reference transcript must not be blank")
    return TranscriptionQuality(
        word_error_rate=float(wer(reference, hypothesis)),
        character_error_rate=float(cer(reference, hypothesis)),
    )
