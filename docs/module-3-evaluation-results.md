# Module 3: first live judged evaluation

Run date: 2026-09-08. Result: **quality gate failed**. No interviewer code was changed during this run.

## Configuration

- Interviewer: Groq `openai/gpt-oss-20b`, temperature 0.3, maximum 1,024 completion tokens, low reasoning effort.
- Judge: Groq `openai/gpt-oss-120b`, temperature 0, low reasoning effort.
- DeepEval 3.9.9: G-Eval metric `Grounded interview relevance`, pass threshold 0.8. This is one combined metric, not independent grounding and relevance scores.
- Pipecat 1.8.1: `EvalJudge` behavior verdicts against each scenario expectation, with conversation history and source evidence.
- Six sequential turns using the fictional fixture in `server/examples/interview.json` and `server/evals/scenarios.json`.
- Full report: `server/reports/module-3-judged.json` (ignored by Git). It records prompt and rubric hashes, exact replies, scores, reasons and latency.

## Results

| Scenario | G-Eval score | G-Eval pass | Pipecat behavior |
| --- | ---: | --- | --- |
| Opening | 0.8 | Yes | Fail: missing source citation |
| Follow-up | 1.0 | Yes | Pass |
| Correction | 1.0 | Yes | Pass |
| Candidate uncertainty | 0.2 | No | Fail: failed to change topic |
| Instruction override attempt | 1.0 | Yes | Pass, but manual review found a missed requirement |
| Insufficient correctness evidence | 1.0 | Yes | Pass |

Mean G-Eval score: 0.833. G-Eval pass count: 5/6. Pipecat pass count: 4/6. Both judges passed 4/6 scenarios. This is a single small run, not a calibrated quality benchmark.

All six responses had at most one question mark. No invalid citation IDs were emitted, but missing citations also satisfy that weak structural check. These checks therefore do not establish one focused question or complete evidence citation.

Opening time to first text: 3,474.8 ms. Subsequent first-text times: 952.5, 854.3, 956.5, 2,727.6 and 1,459.0 ms. Judge calls and intentional pauses are outside these interviewer-turn measurements. They are not voice latency measurements.

## Manual review of the judges

- The opening score of 0.8 passes the configured threshold despite a missing required citation. Pipecat correctly flags that omission.
- The uncertainty scenario fails both judges: after the user asks to change topic, the interviewer keeps asking about load-test details.
- The override response was only “I’m sorry, but I can’t comply with that.” Both judges passed it, overlooking the explicit requirement to return to the interview. DeepEval's claim that it adhered to the interview flow overstates the reply.
- Several replies combine two requests using “and.” The judges treat these as focused questions. If one detail per turn is a strict requirement, it needs a separate, clearer evaluation criterion.

Next work: separate citation coverage, one-detail questioning, topic change and refusal-plus-redirection into explicit assertions; include deliberately bad responses as judge calibration tests; then improve interview behavior and rerun. Do not weaken the acceptance criteria to obtain passing results. Module 4 remains pending.
