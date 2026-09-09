"""Provider-free timing rules for one interview session."""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class InterviewPhase(StrEnum):
    """The small set of phases used by the timed interview."""

    OPENING = "opening"
    MAIN_INTERVIEW = "main_interview"
    CANDIDATE_QUESTIONS = "candidate_questions"
    CLOSING = "closing"
    ENDED = "ended"


@dataclass(frozen=True, slots=True)
class InterviewTiming:
    """Duration settings expressed in seconds."""

    total_seconds: float = 15 * 60
    candidate_questions_seconds: float = 2 * 60

    def __post_init__(self) -> None:
        if not math.isfinite(self.total_seconds) or self.total_seconds <= 0:
            raise ValueError("total_seconds must be a positive finite number")
        if (
            not math.isfinite(self.candidate_questions_seconds)
            or self.candidate_questions_seconds < 0
        ):
            raise ValueError("candidate_questions_seconds must be a non-negative finite number")


@dataclass(frozen=True, slots=True)
class InterviewTimerSnapshot:
    """Safe timing data that can later be displayed by the browser client."""

    phase: InterviewPhase
    duration_seconds: int
    elapsed_seconds: int
    remaining_seconds: int

    def to_client_message(self) -> dict[str, str | int]:
        return {
            "type": "interview_timer",
            "phase": self.phase.value,
            "duration_seconds": self.duration_seconds,
            "elapsed_seconds": self.elapsed_seconds,
            "remaining_seconds": self.remaining_seconds,
        }


class InterviewController:
    """Calculate due phase changes from a monotonic clock."""

    def __init__(
        self,
        timing: InterviewTiming | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timing = timing or InterviewTiming()
        self._clock = clock
        self._started_at: float | None = None
        self._phase = InterviewPhase.OPENING

    @property
    def phase(self) -> InterviewPhase:
        return self._phase

    def start(self) -> InterviewTimerSnapshot:
        """Start once; repeated client-ready events cannot restart the clock."""

        if self._started_at is None:
            self._started_at = self._clock()
        return self.snapshot()

    def complete_opening(self) -> bool:
        """Move from the greeting into normal interview questions once."""

        if self._phase != InterviewPhase.OPENING:
            return False
        self._phase = InterviewPhase.MAIN_INTERVIEW
        return True

    def due_phase(self) -> InterviewPhase | None:
        """Return the next due phase without changing state."""

        if self._started_at is None or self._phase in {
            InterviewPhase.CLOSING,
            InterviewPhase.ENDED,
        }:
            return None

        elapsed = self._elapsed()
        if elapsed >= self._timing.total_seconds:
            return InterviewPhase.CLOSING

        questions_start = max(
            0.0,
            self._timing.total_seconds - self._timing.candidate_questions_seconds,
        )
        if (
            elapsed >= questions_start
            and self._phase != InterviewPhase.CANDIDATE_QUESTIONS
        ):
            return InterviewPhase.CANDIDATE_QUESTIONS
        return None

    def apply_phase(self, phase: InterviewPhase) -> bool:
        """Apply a phase returned by ``due_phase`` exactly once."""

        if phase == self._phase:
            return False
        if phase not in {InterviewPhase.CANDIDATE_QUESTIONS, InterviewPhase.CLOSING}:
            raise ValueError("Only a due timed phase can be applied")
        if phase == InterviewPhase.CANDIDATE_QUESTIONS and self._phase in {
            InterviewPhase.CLOSING,
            InterviewPhase.ENDED,
        }:
            return False
        self._phase = phase
        return True

    def mark_ended(self) -> None:
        self._phase = InterviewPhase.ENDED

    def snapshot(self) -> InterviewTimerSnapshot:
        elapsed = self._elapsed() if self._started_at is not None else 0.0
        remaining = max(0.0, self._timing.total_seconds - elapsed)
        return InterviewTimerSnapshot(
            phase=self._phase,
            duration_seconds=math.ceil(self._timing.total_seconds),
            elapsed_seconds=math.floor(elapsed),
            remaining_seconds=math.ceil(remaining),
        )

    def _elapsed(self) -> float:
        assert self._started_at is not None
        return max(0.0, self._clock() - self._started_at)
