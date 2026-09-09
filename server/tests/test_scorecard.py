import asyncio
import copy
import json

import pytest

from bot import load_example_context
from interviewflow.evaluator import (
    EvaluationError,
    EvaluatorSettings,
    _apply_context_facts,
    _provider_failure,
    _strict_scorecard_response_format,
    _validation_failure,
    evaluate_interview,
)
from interviewflow.scorecard import validate_scorecard
from interviewflow.transcript import Transcript


@pytest.fixture
def sample():
    grounded = load_example_context()
    transcript = Transcript()
    transcript.append("interviewer", "Explain your decision.", "main_interview")
    transcript.append("candidate", "I compared two approaches using a repeatable experiment.", "main_interview")
    rubric = grounded.rubric
    draft = dict(rubric_id=rubric.rubric_id, rubric_version=rubric.version,
                 rubric_hash=rubric.content_hash, reference_sufficiency="insufficient",
                 needs_human_review=False, review_reason=None, criteria=[
        dict(criterion_id=c.criterion_id, applicable=True, score=4, confidence="medium",
             evidence=[dict(turn_id="turn-0002", quote="I compared two approaches")],
             reason="Explained a comparison.", improvement="Explain the outcome.")
        for c in rubric.criteria
    ])
    return grounded, transcript.turns, draft


def test_weighted_score_and_identity(sample):
    grounded, turns, draft = sample
    result = validate_scorecard(json.dumps(draft), grounded, turns, "fake")
    assert result.overall_score == 80.0
    assert result.coverage_percent == 100.0
    assert result.rubric_hash == grounded.rubric.content_hash


@pytest.mark.parametrize("change", [
    lambda d: d.update(rubric_hash="forged"),
    lambda d: d["criteria"].append(copy.deepcopy(d["criteria"][0])),
    lambda d: d["criteria"].pop(),
    lambda d: d["criteria"][0].update(score=True),
    lambda d: d["criteria"][0].update(score=6),
    lambda d: d["criteria"][0].update(score=4.0),
    lambda d: d["criteria"][0].update(evidence=[]),
    lambda d: d["criteria"][0]["evidence"][0].update(quote="Invented achievement"),
    lambda d: d["criteria"][0]["evidence"][0].update(turn_id="unknown"),
    lambda d: d["criteria"][0]["evidence"][0].update(turn_id="turn-0001", quote="Explain"),
    lambda d: d.update(reference_sufficiency="sufficient"),
    lambda d: d.update(overall_score=100),
    lambda d: d["criteria"][0].update(applicable=False),
])
def test_rejects_invalid_or_fabricated_output(sample, change):
    grounded, turns, draft = sample
    change(draft)
    with pytest.raises(ValueError):
        validate_scorecard(json.dumps(draft), grounded, turns, "fake")


def test_unassessed_criteria_excluded_and_empty_score_is_null(sample):
    grounded, turns, draft = sample
    for criterion in draft["criteria"][1:]:
        criterion.update(applicable=False, score=None, evidence=[])
    result = validate_scorecard(json.dumps(draft), grounded, turns, "fake")
    assert result.overall_score == 80
    assert result.coverage_percent < 100
    draft["criteria"][0].update(applicable=False, score=None, evidence=[])
    result = validate_scorecard(json.dumps(draft), grounded, turns, "fake")
    assert result.overall_score is None
    assert result.needs_human_review


def test_uncertain_transcript_can_withhold_scores(sample):
    grounded, turns, draft = sample
    draft.update(needs_human_review=True, review_reason="Unclear transcription")
    for c in draft["criteria"]:
        c.update(score=None, evidence=[])
    assert validate_scorecard(json.dumps(draft), grounded, turns, "fake").overall_score is None


def test_candidate_questions_cannot_support_scores(sample):
    grounded, turns, draft = sample
    turns = (turns[0], turns[1].model_copy(update={"phase": "candidate_questions"}))
    with pytest.raises(ValueError):
        validate_scorecard(json.dumps(draft), grounded, turns, "fake")


def test_transcript_preserves_exact_text_and_ignores_empty():
    transcript = Transcript()
    transcript.append("candidate", "  ", "main_interview")
    transcript.append("candidate", " My answer. ", "main_interview")
    assert len(transcript.turns) == 1
    assert transcript.turns[0].text == " My answer. "


def test_evaluator_runs_once_and_validates_response(sample):
    grounded, turns, draft = sample
    class Fake:
        calls = 0
        async def run_inference(self, context, system_instruction):
            self.calls += 1
            assert context.get_messages()[0]["role"] == "user"
            assert "untrusted evidence" in system_instruction
            return json.dumps(draft)
    fake = Fake()
    result = asyncio.run(evaluate_interview(grounded, turns, EvaluatorSettings("fake"), service=fake))
    assert result.overall_score == 80
    assert fake.calls == 1


def test_evaluator_uses_strict_complete_json_schema():
    response_format = _strict_scorecard_response_format()
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True

    def assert_objects_are_strict(node):
        if isinstance(node, dict):
            if isinstance(node.get("properties"), dict):
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            assert "default" not in node
            for value in node.values():
                assert_objects_are_strict(value)
        elif isinstance(node, list):
            for value in node:
                assert_objects_are_strict(value)

    assert_objects_are_strict(response_format["json_schema"]["schema"])


@pytest.mark.parametrize(
    "status,code",
    [(429, "EVALUATOR_LIMIT"), (401, "EVALUATOR_ACCESS"),
     (400, "EVALUATOR_REQUEST"), (None, "EVALUATOR_PROVIDER")],
)
def test_provider_failures_have_safe_codes(status, code):
    actual_code, message = _provider_failure(status)
    assert actual_code == code
    assert message


def test_validation_failures_expose_only_allowlisted_rules():
    assert _validation_failure(ValueError(
        "Evidence must exactly quote an assessment answer"
    )) == "EVIDENCE_QUOTE"
    assert _validation_failure(ValueError("private model output")) == "SCHEMA"


def test_absent_references_force_insufficient_reference_sufficiency(sample):
    grounded, _, draft = sample
    draft["reference_sufficiency"] = "sufficient"

    normalized = json.loads(_apply_context_facts(json.dumps(draft), grounded))

    assert normalized["reference_sufficiency"] == "insufficient"


@pytest.mark.parametrize("response", ["", "not json", '{"secret":"private"}'])
def test_provider_bad_output_returns_safe_error(sample, response):
    grounded, turns, _ = sample
    class Fake:
        async def run_inference(self, *args, **kwargs):
            return response
    with pytest.raises(EvaluationError, match="invalid scorecard") as error:
        asyncio.run(evaluate_interview(grounded, turns, EvaluatorSettings("fake"), service=Fake()))
    assert "private" not in str(error.value)


def test_no_answers_or_oversized_input_never_calls_provider(sample):
    grounded, turns, _ = sample
    with pytest.raises(EvaluationError, match="No candidate"):
        asyncio.run(evaluate_interview(grounded, (), EvaluatorSettings("fake")))
    with pytest.raises(EvaluationError, match="too large"):
        asyncio.run(evaluate_interview(grounded, turns, EvaluatorSettings("fake", max_input_bytes=1)))


def test_timeout_is_safe_and_has_no_unbounded_retry(sample):
    grounded, turns, _ = sample
    class Slow:
        async def run_inference(self, *args, **kwargs):
            await asyncio.sleep(1)
    with pytest.raises(EvaluationError, match="timed out"):
        asyncio.run(evaluate_interview(grounded, turns,
                    EvaluatorSettings("fake", timeout_seconds=0.01), service=Slow()))


def test_warnings_require_human_review(sample):
    grounded, turns, draft = sample
    turns = (turns[0], turns[1].model_copy(update={"warnings": ("uncertain STT",)}))
    with pytest.raises(ValueError, match="Uncertain evidence"):
        validate_scorecard(json.dumps(draft), grounded, turns, "fake")


def test_contradiction_requires_two_real_candidate_turns(sample):
    grounded, turns, draft = sample
    draft.update(consistency_note="Inconsistent claims", needs_human_review=True,
                 review_reason="Review contradiction", consistency_evidence=[
                     dict(turn_id="turn-0002", quote="I compared two approaches")])
    with pytest.raises(ValueError, match="two turns"):
        validate_scorecard(json.dumps(draft), grounded, turns, "fake")


def test_bot_scores_only_after_voice_finishes(monkeypatch, sample):
    import bot
    grounded, turns, _ = sample
    from types import SimpleNamespace
    events = []
    async def voice(*args, **kwargs):
        events.append("voice_completed")
        return SimpleNamespace(turns=turns)
    async def evaluator(*args):
        events.append("evaluated")
        return "scorecard"
    monkeypatch.setattr(bot, "load_example_context", lambda: grounded)
    monkeypatch.setattr(bot, "load_settings", lambda: SimpleNamespace(interview_duration_minutes=15))
    monkeypatch.setattr(bot, "load_interviewer_settings", lambda: None)
    monkeypatch.setattr(bot, "load_voice_settings", lambda: None)
    monkeypatch.setattr(bot, "load_evaluator_settings", lambda: None)
    monkeypatch.setattr(bot, "create_voice_services", lambda _: None)
    monkeypatch.setattr(bot, "run_voice_interview", voice)
    monkeypatch.setattr(bot, "evaluate_interview", evaluator)
    assert asyncio.run(bot.bot(None)) == "scorecard"
    assert events == ["voice_completed", "evaluated"]
