"""Validate evidence and calculate rubric totals using ordinary Python."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from interviewflow.grounded_context import GroundedContext
from interviewflow.transcript import TranscriptTurn


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Evidence(StrictModel):
    turn_id: str
    quote: str = Field(min_length=1)


class CriterionResult(StrictModel):
    criterion_id: str
    applicable: bool
    score: int | None = Field(ge=1, le=5)
    confidence: Literal["high", "medium", "low"]
    evidence: list[Evidence]
    reason: str = Field(min_length=1)
    improvement: str


class EvaluationDraft(StrictModel):
    rubric_id: str
    rubric_version: int
    rubric_hash: str
    reference_sufficiency: Literal["sufficient", "partial", "insufficient", "not_required"]
    needs_human_review: bool
    review_reason: str | None
    criteria: list[CriterionResult]
    consistency_evidence: list[Evidence] = Field(default_factory=list)
    consistency_note: str | None = None


class Scorecard(EvaluationDraft):
    overall_score: float | None
    coverage_percent: float
    evaluator_model: str


def validate_scorecard(raw: str, grounded: GroundedContext,
                       turns: tuple[TranscriptTurn, ...], model: str) -> Scorecard:
    draft = EvaluationDraft.model_validate_json(raw)
    rubric = grounded.rubric
    if (draft.rubric_id, draft.rubric_version, draft.rubric_hash) != (
        rubric.rubric_id, rubric.version, rubric.content_hash,
    ):
        raise ValueError("Scorecard rubric does not match the approved rubric")
    expected = {c.criterion_id: c for c in rubric.criteria}
    ids = [c.criterion_id for c in draft.criteria]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Every approved criterion must appear exactly once")
    sources = {t.turn_id: t for t in turns}
    if len(sources) != len(turns):
        raise ValueError("Transcript turn IDs must be unique")
    if draft.consistency_evidence or draft.consistency_note:
        if (len({e.turn_id for e in draft.consistency_evidence}) < 2
                or not (draft.consistency_note or "").strip() or not draft.needs_human_review):
            raise ValueError("Contradictions require two turns, an explanation and human review")
        for e in draft.consistency_evidence:
            turn = sources.get(e.turn_id)
            if turn is None or turn.role != "candidate" or not e.quote.strip() or e.quote not in turn.text:
                raise ValueError("Contradiction evidence must exactly quote candidate turns")
    if not any(s.kind == "technical_reference" for s in grounded.sources):
        if draft.reference_sufficiency in {"sufficient", "partial"}:
            raise ValueError("Technical references are absent")
    weighted = weight = 0.0
    for result in draft.criteria:
        if not result.applicable:
            if result.score is not None or result.evidence:
                raise ValueError("Non-applicable criteria cannot have a score or evidence")
            continue
        for evidence in result.evidence:
            turn = sources.get(evidence.turn_id)
            if (turn is None or turn.role != "candidate"
                    or turn.phase not in {"opening", "main_interview"}
                    or not evidence.quote.strip() or evidence.quote not in turn.text):
                raise ValueError("Evidence must exactly quote an assessment answer")
        if result.score is None:
            if not draft.needs_human_review:
                raise ValueError("Unscorable applicable criteria require human review")
            continue
        if not result.evidence:
            raise ValueError("Scored criteria require candidate evidence")
        if any(sources[e.turn_id].warnings or sources[e.turn_id].interrupted for e in result.evidence):
            if not draft.needs_human_review:
                raise ValueError("Uncertain evidence requires human review")
        criterion_weight = expected[result.criterion_id].weight
        weighted += result.score / 5 * criterion_weight
        weight += criterion_weight
    if draft.needs_human_review and not (draft.review_reason or "").strip():
        raise ValueError("Human review requires an explanation")
    if not weight:
        draft.needs_human_review = True
        draft.review_reason = draft.review_reason or "Insufficient evidence to calculate a score."
    return Scorecard(**draft.model_dump(),
                     overall_score=round(100 * weighted / weight, 1) if weight else None,
                     coverage_percent=round(100 * weight / sum(c.weight for c in rubric.criteria), 1),
                     evaluator_model=model)
