# Module 6 — Evidence-backed scorecards

The evaluator reads the whole interview once and produces one result per approved
competency. Python checks the evidence and calculates weighted totals. Scorecard
generation runs after the voice session ends, so it does not slow spoken replies.

## Files and responsibilities

- `transcript.py`: collects finalized Pipecat turns in memory, with IDs, timestamps,
  speaker, phase and interruption metadata. No audio or transcript files are saved.
- `evaluator.py`: sends documents, rubric and transcript to the approved Groq
  evaluator (`openai/gpt-oss-120b`, configurable as `GROQ_EVALUATOR_MODEL`). It makes
  one inference call with a 60-second timeout, requests strict JSON-schema output,
  and uses a 2,048-token completion ceiling to leave room for the interview input.
  Failures are classified with safe codes without logging candidate text.
- `scorecard.py`: Pydantic checks JSON types and required fields. Additional Python
  checks verify rubric identity, unique criteria, real candidate turn IDs and exact
  quotation text. It rejects unsupported output rather than creating a default score.
- `voice_pipeline.py`: subscribes to finalized turn events and returns the transcript.
- `bot.py`: evaluates after the voice runner finishes and returns a scorecard object.
  The current runner does not display or persist that return value; Module 7 must
  connect it to session results and the scorecard screen. Failed calls log only a
  safe operational error.

## Score meaning

Each criterion gets an integer 1–5 using its approved anchors. Non-applicable
criteria have no score. An applicable but unreliable answer may also have no score,
with an explanation requiring human review. Python computes the weighted total from
scored criteria only. Coverage reports how much of the rubric weight was scored.
If nothing is scorable, the overall score is null. Any human-review flag means the
scorecard is provisional, including any numerical total.

Exact-quote validation proves that a quotation exists; it cannot prove that the
LLM's interpretation is fair. Technical correctness still needs approved reference
material. Contradictions require quotations from at least two candidate turns and
human review. Candidate questions and closing remarks are excluded as scoring evidence.

The evaluator prompt is now a full-interview adaptation of the earlier answer-level
specification. Its executable source is `evaluator.py`; there is no extra API call
for each answer. The output schema is in `scorecard.py`.

## Run independently

From `interviewflow-ai/server`, test without API calls:

```powershell
uv --cache-dir ..\.uv-cache run pytest -q tests/test_scorecard.py tests/test_voice_pipeline.py tests/test_voice_bot.py
```

To deliberately run one fictional evaluation (uses Groq credits):

```powershell
uv --cache-dir ..\.uv-cache run python scripts/evaluate_scorecard.py --case concrete
```

Add `--judge` with `GROQ_JUDGE_MODEL` explicitly set to run three DeepEval G-Eval
metrics and a Pipecat EvalJudge verdict. This adds at least four judge calls; DeepEval
may make additional internal calls. G-Eval threshold is 0.8 for evidence faithfulness,
rubric alignment and feedback relevance. Inputs are sources/transcript, actual
scorecard and scenario expectation. The printed JSON contains model, prompt/rubric
hashes, scores, thresholds, verdicts and reasons. Same-provider judge bias remains.
These are scorecard component evaluations, not browser/audio end-to-end tests.

Eight fictional scenarios cover concrete evidence, vague claims, uncertainty,
contradiction, correction, injection, poor transcription and missing references.
They are draft regression cases awaiting user review, not calibrated gold labels.

For your own finalized transcript JSON (a list of `TranscriptTurn` records):

```powershell
uv --cache-dir ..\.uv-cache run python scripts/generate_scorecard.py --inputs examples/interview.json --transcript examples/transcript.json --approve-rubric
```

The input file contains `resume_text`, `job_description`, and `rubric`, plus optional
explicitly approved `references`. Review these before using `--approve-rubric`.
The included transcript is fictional; replace its path with your own file to test real data.
This command deliberately prints the resulting scorecard, which contains quotations.
Application logs do not contain interview text. Input exceeding the conservative
48 KB request budget fails without truncating evidence. Long transcripts and provider
token limits may require a later, separately measured batching design.

## Verification status

Verified: 31 focused tests and 124 full regression tests passed. Offline tests check scoring, coverage, unknown/duplicate criteria, quote fabrication,
role/phase provenance, uncertain evidence, contradictions, malformed responses,
timeout handling, transcript events and post-call orchestration. Live Groq/DeepEval/
Pipecat judge results have not yet been measured for this module. Pipecat's one-shot
inference currently returns text without usage counts; only call duration/model and
outcome are logged here, not an invented token or cost estimate.
