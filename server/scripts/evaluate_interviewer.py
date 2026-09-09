"""Run fictional multi-turn regression scenarios, with explicitly enabled judges."""

import argparse
import asyncio
import json
import hashlib
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interviewflow.logging_setup import configure_logging

configure_logging()
os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_OUT"] = "YES"

from chat_interview import load_inputs
from interviewflow.config import DEFAULT_ENV_FILE
from interviewflow.interviewer import INTERVIEW_INSTRUCTIONS, load_interviewer_settings
from interviewflow.interview_session import InterviewSession


async def evaluate(args):
    settings = load_interviewer_settings(args.env_file)
    judge_model = os.getenv("GROQ_JUDGE_MODEL", "")
    if args.judge and not judge_model:
        raise ValueError("Set GROQ_JUDGE_MODEL explicitly before enabling judge calls")
    grounded = load_inputs(args)
    scenarios = json.loads((args.inputs.parent.parent / "evals/scenarios.json").read_text())
    session = InterviewSession(grounded, settings)
    judge = None
    if args.judge:
        from evals.groq_judge import GroqJudge
        from pipecat.evals.judge import EvalJudge
        judge = GroqJudge(settings.api_key, judge_model)
        behavioral_judge = EvalJudge(judge.service, max_tokens=1024)
        behavioral_judge.add_user_message("Interview evidence: " + grounded.to_messages()[1]["content"])
    report = {"completed": False, "model": settings.model, "judge_model": judge_model if args.judge else None,
              "prompt_hash": hashlib.sha256(INTERVIEW_INSTRUCTIONS.encode()).hexdigest(),
              "rubric_hash": grounded.rubric.content_hash, "data": "fictional", "turns": []}
    known_ids = {source.source_id for source in grounded.sources}
    try:
        await session.start()
        for scenario in scenarios:
            reply = await session.reply(scenario["answer"])
            cited = re.findall(r"\[([^\[\]]+)\]", reply.text)
            valid_citation_ids = all(value in known_ids for value in cited)
            citation_requirement_met = (
                valid_citation_ids and (not scenario.get("requires_citation") or bool(cited))
            )
            question_sentences = [
                sentence for sentence in re.split(r"(?<=[?.!])\s+", reply.text)
                if "?" in sentence
            ]
            single_target_shape = all(
                " and " not in sentence.lower() for sentence in question_sentences
            )
            question_requirement_met = (
                not scenario.get("requires_question") or reply.text.count("?") == 1
            )
            row = {"scenario": scenario["name"], "answer": scenario["answer"],
                   "expectation": scenario["expectation"], **asdict(reply),
                   "at_most_one_question_mark": reply.text.count("?") <= 1,
                   "valid_citation_ids": valid_citation_ids,
                   "citation_requirement_met": citation_requirement_met,
                   "question_requirement_met": question_requirement_met,
                   "single_target_shape": single_target_shape,
                   "semantic_evaluation": "not_run"}
            if judge:
                from deepeval.metrics import GEval
                from deepeval.test_case import LLMTestCase, SingleTurnParams
                behavioral_judge.add_user_message(scenario["answer"])
                behavioral_judge.add_assistant_message(reply.text)
                verdict = await asyncio.wait_for(behavioral_judge.evaluate(scenario["expectation"]), 30)
                row["pipecat_behavior"] = {"passed": verdict.passed, "reason": verdict.reason}
                metric = GEval(
                    name="Grounded interview relevance", model=judge, threshold=0.8,
                    evaluation_steps=[
                        "Compare the reply with the evidence and conversation in input. Penalize invented candidate facts and unsupported correctness judgments.",
                        "Check expected_output for the scenario goal. Check the reply addresses the latest answer naturally with at most one focused question and accepts corrections.",
                    ],
                    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                                       SingleTurnParams.EXPECTED_OUTPUT],
                )
                test_case = LLMTestCase(
                    input=json.dumps(session.context.get_messages()[:-1], ensure_ascii=False),
                    actual_output=reply.text, expected_output=scenario["expectation"],
                )
                await asyncio.wait_for(metric.a_measure(test_case), 60)
                row["deepeval"] = {"score": metric.score, "passed": metric.is_successful(), "reason": metric.reason}
                row["semantic_evaluation"] = "completed"
            report["turns"].append(row)
            print(f"{scenario['name']}: first text {reply.first_text_ms:.0f} ms; "
                  f"question_check={row['question_requirement_met']}; "
                  f"citation_check={row['citation_requirement_met']}; "
                  f"single_target_shape={row['single_target_shape']}")
            # Pace deliberate tests against free-tier token/request limits.
            if args.judge:
                await asyncio.sleep(10)
        report["completed"] = True
    finally:
        await session.close()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return all(row["at_most_one_question_mark"] and row["citation_requirement_met"]
               and row["question_requirement_met"] and row["single_target_shape"] and (
        not args.judge or (row["pipecat_behavior"]["passed"] and row["deepeval"]["passed"])
    ) for row in report["turns"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output", type=Path, default=root / "reports/module-3.json")
    parser.add_argument("--approve-rubric", action="store_true")
    parser.add_argument("--judge", action="store_true", help="Enable extra Groq calls for Pipecat and DeepEval judges")
    args = parser.parse_args()
    args.inputs = root / "examples/interview.json"
    args.resume = None
    try:
        return 0 if asyncio.run(evaluate(args)) else 1
    except Exception as error:
        print(f"Evaluation did not complete ({type(error).__name__}); inspect configuration and provider limits.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
