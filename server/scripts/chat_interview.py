"""Run a grounded text interview from the terminal."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from interviewflow.logging_setup import configure_logging

configure_logging()

from interviewflow.config import DEFAULT_ENV_FILE
from interviewflow.grounded_context import TechnicalReference, build_grounded_context
from interviewflow.interview_session import InterviewError, InterviewSession
from interviewflow.interviewer import load_interviewer_settings
from interviewflow.resume_ingestion import ResumeDocument, ResumePage, ingest_resume_pdf
from interviewflow.rubric import load_approved_rubric


def load_inputs(args):
    data = json.loads(args.inputs.read_text(encoding="utf-8"))
    rubric = load_approved_rubric(data["rubric"], human_approved=args.approve_rubric)
    if args.resume:
        resume = ingest_resume_pdf(args.resume.read_bytes())
    else:
        text = data["resume_text"]
        resume = ResumeDocument("fictional-demo", len(text.encode()), 1,
                                (ResumePage(1, text),), text)
    references = tuple(TechnicalReference(**ref) for ref in data.get("references", []))
    return build_grounded_context(resume, data["job_description"], rubric, references)


async def chat(args):
    grounded = load_inputs(args)
    settings = load_interviewer_settings(args.env_file)
    session = InterviewSession(grounded, settings)
    print("Interview text and documents will be sent to Groq. Type /quit to end.")
    try:
        await session.start()
        answer = "Please start the practice interview."
        while True:
            print("\nInterviewer: ", end="", flush=True)
            reply = await session.reply(answer, on_text=lambda text: print(text, end="", flush=True))
            print(f"\n[First text: {reply.first_text_ms:.0f} ms; full reply: {reply.total_ms:.0f} ms]")
            if args.smoke:
                break
            try:
                answer = await asyncio.to_thread(input, "\nYou: ")
            except EOFError:
                break
            if answer.strip().lower() == "/quit":
                break
            while not answer.strip():
                answer = await asyncio.to_thread(input, "Please enter an answer (or /quit): ")
            if answer.strip().lower() == "/quit":
                break
    finally:
        await session.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path,
                        default=Path(__file__).resolve().parents[1] / "examples/interview.json")
    parser.add_argument("--resume", type=Path, help="Optional real resume PDF, replacing demo resume text")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--approve-rubric", action="store_true", help="Confirm you reviewed the input rubric")
    parser.add_argument("--smoke", action="store_true", help="Generate one opening reply and exit")
    args = parser.parse_args()
    try:
        asyncio.run(chat(args))
    except (InterviewError, ValueError, KeyError, OSError) as error:
        # Third-party exceptions can contain document bodies. Only our safe error is printed.
        message = str(error) if isinstance(error, InterviewError) else "Check the input files, rubric approval and Groq configuration."
        print(f"\nInterview stopped: {message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterview ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
