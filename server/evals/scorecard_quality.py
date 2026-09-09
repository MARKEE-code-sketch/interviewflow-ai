"""Explicit optional LLM judges for scorecard quality; no live calls on import."""

import asyncio
import json


async def judge_scorecard(grounded, turns, scorecard, expectation, judge):
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, SingleTurnParams
    from pipecat.evals.judge import EvalJudge

    evidence = json.dumps({"sources": grounded.to_messages()[1]["content"],
                           "transcript": [t.model_dump() for t in turns]})
    output = scorecard.model_dump_json()
    results = {}
    for name, instruction in {
        "evidence_faithfulness": "Every evaluative claim must follow from cited candidate evidence; exact quotes alone do not prove the claim. No invented correctness or dishonesty judgments.",
        "rubric_alignment": "Check applicability and scores against the approved criterion anchors. Repetition must not inflate scores. Unasked competencies must not be penalized.",
        "feedback_relevance": "Check that reasons and actionable improvements fit the actual answers and expected behavior. Ignore protected traits and transcription mistakes when scoring ability.",
    }.items():
        metric = GEval(name=name, model=judge, threshold=0.8,
                       evaluation_steps=[instruction, "Check the expected behavior supplied in expected_output."],
                       evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                                          SingleTurnParams.EXPECTED_OUTPUT])
        case = LLMTestCase(input=evidence, actual_output=output, expected_output=expectation)
        await asyncio.wait_for(metric.a_measure(case), 60)
        results[name] = dict(score=metric.score, passed=metric.is_successful(), reason=metric.reason,
                             threshold=0.8)
    behavioral = EvalJudge(judge.service)
    behavioral.add_user_message(evidence)
    behavioral.add_assistant_message(output)
    verdict = await asyncio.wait_for(behavioral.evaluate(expectation), 60)
    results["pipecat"] = {"passed": verdict.passed, "reason": verdict.reason}
    return results
