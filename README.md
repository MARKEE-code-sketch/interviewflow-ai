# InterviewFlow AI

InterviewFlow AI is an English voice interview coach grounded in a candidate's resume, a job description, an approved rubric, and the interview transcript.

The project is being built module by module. Read `blueprint.md` for the architecture and evaluation gates.

## Current status

Modules 0–2 provide the Python foundation, validated resume PDF extraction, and a grounded context builder with immutable approved rubrics. Module 3 adds the Groq text interviewer. Module 4 adds the English SmallWebRTC voice pipeline with Deepgram STT/TTS, local turn detection, interruptions, safe metrics and STT scoring. Live provider verification is the next gate. See the [Module 4 walkthrough](docs/module-4-voice-pipeline.md).

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
