"""Keep finalized interview turns in memory; never write their text to logs."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TranscriptTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    turn_id: str = Field(min_length=1)
    role: Literal["candidate", "interviewer"]
    text: str = Field(min_length=1)
    phase: str
    timestamp: str
    interrupted: bool = False
    warnings: tuple[str, ...] = ()


class Transcript:
    def __init__(self):
        self._turns: list[TranscriptTurn] = []

    @property
    def turns(self) -> tuple[TranscriptTurn, ...]:
        return tuple(self._turns)

    def append(self, role, text, phase, *, timestamp=None, interrupted=False):
        if not text or not text.strip():
            return
        self._turns.append(TranscriptTurn(
            turn_id=f"turn-{len(self._turns) + 1:04d}", role=role, text=text,
            phase=str(phase), timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            interrupted=interrupted,
        ))

    def append_candidate_fragment(self, text, phase, *, timestamp=None):
        """Combine consecutive STT fragments into one candidate answer."""

        if not text or not text.strip():
            return
        phase = str(phase)
        if self._turns and self._turns[-1].role == "candidate" and self._turns[-1].phase == phase:
            previous = self._turns[-1]
            self._turns[-1] = TranscriptTurn(
                turn_id=previous.turn_id,
                role=previous.role,
                text=f"{previous.text.rstrip()} {text.strip()}",
                phase=previous.phase,
                timestamp=previous.timestamp,
                interrupted=previous.interrupted,
                warnings=previous.warnings,
            )
            return
        self.append("candidate", text, phase, timestamp=timestamp)
