# InterviewFlow AI

InterviewFlow AI is an English voice interview coach grounded in a candidate's resume, a job description, an approved rubric, and the interview transcript.

The project is being built module by module. Read `blueprint.md` for the architecture and evaluation gates.

## Current status

Modules 0–7 provide resume ingestion, grounded context, the Groq interviewer, Deepgram voice pipeline, interview timer, evidence-backed scorecard, and React client. Module 8 adds SQLite/PostgreSQL persistence, Daily transport selection, Docker, CI, and a Render Blueprint. The remaining gate is a live Render deployment smoke test. See the [Module 8 walkthrough](docs/module-8-production.md).

## Project layout

```text
interviewflow-ai/
├── server/                 Python backend
│   ├── interviewflow/      Application package
│   └── tests/              Backend tests
├── AGENTS.md               Project working rules
├── blueprint.md            Approved architecture and module plan
└── .env.example            Safe configuration template
```

## Verify Module 0

From `interviewflow-ai/server`:

```powershell
$env:UV_CACHE_DIR = "..\.uv-cache"
uv sync
uv run pytest
```

## Check a resume locally

From `interviewflow-ai/server`, provide any local PDF path:

```powershell
uv run python scripts/check_resume.py "C:\path\to\resume.pdf"
```

The command displays the extracted text for manual review. It does not save or upload the PDF.

## Verify Module 2

From `interviewflow-ai/server`:

```powershell
uv run pytest -q tests/test_rubric.py tests/test_grounded_context.py
```

Read the [Module 2 walkthrough](docs/module-2-grounded-context.md) for what each block does.

## Try Module 3

Read the [Module 3 walkthrough](docs/module-3-text-interviewer.md) for setup, rubric review, terminal commands and measured limitations. From `interviewflow-ai/server`, after reviewing `examples/interview.json` and setting the Groq key:

```powershell
uv run python scripts/chat_interview.py --approve-rubric
```

## Try Module 4

After adding Groq and Deepgram keys to `.env`, run from `interviewflow-ai/server`:

```powershell
uv run python bot.py -t webrtc
```

Open `http://localhost:7860/client`. The voice walkthrough contains the test script and WER/CER command.

## Module 5

The server controls the 15-minute interview lifecycle, reserves the final two minutes for candidate questions, and publishes timer snapshots to the React client. The LLM cannot terminate a session; only the server deadline or the client's End Interview action can do so. Read the [Module 5 walkthrough](docs/module-5-interview-controller.md) for the code map and test commands.

## Module 6

The post-interview evaluator creates a validated rubric scorecard using Groq 120B. Read the [Module 6 walkthrough](docs/module-6-scorecard.md) for code explanations, offline tests, and deliberately invoked live evaluation commands. The scorecard UI comes in Module 7.

## Module 8

Local development uses SmallWebRTC and SQLite. The hosted configuration uses Daily WebRTC and PostgreSQL without changing the core interview pipeline. Read the [Module 8 walkthrough](docs/module-8-production.md) for the data lifecycle, verification commands, required secrets, and Render deployment steps.
