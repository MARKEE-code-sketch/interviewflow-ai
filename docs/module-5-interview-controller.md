# Module 5 — Interview Controller

## What it does

Module 5 gives every interview a reliable duration and four phases:

1. `opening` — the interviewer greets the candidate and asks the first question.
2. `main_interview` — normal resume- and role-grounded questions.
3. `candidate_questions` — the final two minutes are reserved for the candidate.
4. `closing` — Pipecat speaks a fixed closing sentence and ends gracefully.

The normal 15-minute schedule changes to candidate questions at minute 13 and closes at minute 15.

## Why the server owns the clock

The server uses Python's monotonic clock. It measures elapsed time and is not affected if the computer's displayed date or time changes. The future React client receives only duration, elapsed seconds, remaining seconds, and phase. It will display the countdown, but it will not control the deadline.

## Code map

### `interview_controller.py`

This is the provider-free decision layer. It knows the start time, current phase, deadline, and whether an early ending was requested. It does not import Pipecat, Groq, Deepgram, or React. A fake clock can therefore test 15 minutes instantly.

`due_phase()` reports a transition without changing state. The Pipecat adapter applies the phase only after it successfully queues the required frames. This prevents a failed queue operation from silently losing a transition.

### `interview_lifecycle.py`

This is the small Pipecat adapter. It:

- tracks whether the user or assistant is speaking;
- waits for a safe boundary instead of cutting off speech;
- appends the candidate-questions instruction with `LLMMessagesAppendFrame`;
- sends timer snapshots through RTVI for the future frontend;
- queues `TTSSpeakFrame` followed by `EndFrame` for graceful closing;
- keeps termination outside the LLM so an incorrect tool call cannot end early.

The server's monotonic deadline is the automatic termination authority. The frontend's explicit End Interview action disconnects the session when the candidate chooses to finish early. The interviewer LLM has no termination tool.

### `voice_pipeline.py`

The existing audio pipeline order is unchanged. The orchestrator creates the controller, attaches the lifecycle event handlers, and starts the managed timer when the RTVI client is ready. Pipecat's incomplete-turn filter prevents a response when a candidate is still mid-thought.

### `bot.py`

The configured `INTERVIEW_DURATION_MINUTES` value is converted to seconds and passed to the pipeline. The default remains 15 minutes.

## Timer message prepared for Module 7

The server sends a safe message shaped like this:

```json
{
  "type": "interview_timer",
  "phase": "main_interview",
  "duration_seconds": 900,
  "elapsed_seconds": 25,
  "remaining_seconds": 875
}
```

It does not expose the raw monotonic start value. Module 7 will use this message to render and periodically correct a smooth countdown.

## Run the Module 5 tests

From `interviewflow-ai/server`:

```powershell
uv --cache-dir ..\.uv-cache run pytest -q tests/test_interview_controller.py tests/test_voice_pipeline.py tests/test_interviewer_prompt.py
```

Expected result: `12 passed`.

Run all regression tests:

```powershell
uv --cache-dir ..\.uv-cache run pytest -q
```

Current verified result: `96 passed`.

## Remaining live check

For a quick live check without waiting 15 minutes, temporarily set `INTERVIEW_DURATION_MINUTES=1` in the local `.env`, run the bot, and confirm that it enters candidate questions immediately and closes near one minute without interrupting active speech. Restore the value to `15` afterward. This consumes provider credits and is intentionally not part of the offline test suite.
