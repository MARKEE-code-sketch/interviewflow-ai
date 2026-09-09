"""Verify the optional evaluator adapter without spending provider credits."""

import asyncio
import os

import pytest
from pydantic import BaseModel

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_OUT"] = "YES"
pytest.importorskip("deepeval")

from evals.groq_judge import GroqJudge


class Verdict(BaseModel):
    score: int


class FakeService:
    async def run_inference(self, context, system_instruction):
        assert "JSON schema" in system_instruction
        return '{"score": 8}'


def test_schema_aware_judge_returns_validated_data():
    judge = GroqJudge("fake", "test-model")
    judge.service = FakeService()
    assert asyncio.run(judge.a_generate("Evaluate test data", Verdict)).score == 8


def test_deepeval_metric_and_pipecat_judge_construct_without_default_provider():
    from deepeval.metrics import GEval
    from deepeval.test_case import SingleTurnParams
    from pipecat.evals.judge import EvalJudge

    judge = GroqJudge("fake", "explicit-model")
    metric = GEval(
        name="Grounding", model=judge, evaluation_steps=["Check evidence support"],
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
    )
    assert metric.model is judge
    assert EvalJudge(judge.service) is not None
