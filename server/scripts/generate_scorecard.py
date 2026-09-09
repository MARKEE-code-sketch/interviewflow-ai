"""Generate a scorecard from reviewed interview inputs and a finalized transcript."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interviewflow.logging_setup import configure_logging
from interviewflow.evaluator import evaluate_interview, load_evaluator_settings
from interviewflow.grounded_context import build_grounded_context, TechnicalReference
from interviewflow.resume_ingestion import ResumeDocument, ResumePage
from interviewflow.rubric import load_approved_rubric
from interviewflow.transcript import TranscriptTurn


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--approve-rubric", action="store_true")
    args = parser.parse_args()
    configure_logging()
    try:
        data = json.loads(args.inputs.read_text(encoding="utf-8"))
        text = data["resume_text"]
        resume = ResumeDocument("cli-input", len(text.encode()), 1, (ResumePage(1, text),), text)
        rubric = load_approved_rubric(data["rubric"], human_approved=args.approve_rubric)
        references = tuple(TechnicalReference(**r) for r in data.get("references", []))
        grounded = build_grounded_context(resume, data["job_description"], rubric, references)
        turns = tuple(TranscriptTurn.model_validate_json(json.dumps(t)) for t in
                      json.loads(args.transcript.read_text(encoding="utf-8")))
        scorecard = asyncio.run(evaluate_interview(grounded, turns, load_evaluator_settings()))
        print(scorecard.model_dump_json(indent=2))
        return 0
    except Exception:
        print("Scorecard unavailable. Check input schema, rubric approval and provider access.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
