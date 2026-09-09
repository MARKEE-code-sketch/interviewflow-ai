# InterviewFlow AI Instructions

All behavioral, critical, safety, privacy, secret-handling, teaching, and verification instructions in `../AGENTS.md` remain mandatory. This file extends them for `interviewflow-ai/`; it does not modify or replace the parent file.

The parent file's project-specific section describes the archived Adaptive English-Hindi Voice Agent. For files inside this folder only, the project-specific rules below define the current project.

## Project goal

- Build the document-grounded Voice Interview Coach defined in `blueprint.md`.
- Build and verify the complete English MVP before considering Hindi.
- The MVP is a browser-based, 15-minute interview grounded in an uploaded resume PDF and a supplied job description.
- Keep the code compatible with Pipecat's standard runner and Pipecat Cloud deployment pattern.
- Treat `blueprint.md` as the scope and architecture reference. Update it only after the user approves a changed technical decision.

## Human-in-the-loop workflow

- Before implementing each module, explain in simple language what it does, why it is needed, the proposed technology, and the success check.
- Wait for explicit user approval before implementing that module.
- If Pipecat behavior or APIs are unclear, consult the current official documentation and official examples. If they cannot be accessed, stop and ask the user to provide the relevant documentation text.
- Do not guess Pipecat APIs or recreate a supported Pipecat feature without a clear reason.

## Architecture boundaries

- Use Pipecat's normal cascaded pipeline: transport -> STT -> user context -> LLM -> TTS -> transport -> assistant context.
- Do not introduce a custom conversation state machine or per-turn JSON extraction layer unless tests demonstrate that Pipecat context and tool calling cannot satisfy a specific requirement.
- Candidate-specific statements must be grounded in the resume, job description, approved rubric, or interview transcript.
- Scorecard findings must include evidence references. When evidence is absent, report insufficient evidence rather than inventing a conclusion.
- For the MVP, prefer passing the complete validated resume and job description to the LLM when they fit safely in context. Do not add a vector database without a measured need.
- Raw interview audio retention is disabled by default. Transcript retention and deletion behavior must be visible to the user before production deployment.

## Evaluation rules

- Test each module independently before connecting it to the next module.
- Use deterministic pytest checks for parsing, validation, timers, storage, and security behavior.
- Use DeepEval for grounding, relevance, and multi-turn quality where an LLM judge is appropriate.
- Use Pipecat Evals for real agent behavior, context, interruption, tool-call, and latency scenarios.
- Use audio metrics such as WER/CER only for speech recognition, not for judging interview quality.
- LLM-as-a-judge scores are signals, not absolute truth. Maintain a small human-reviewed regression set.
- Do not publish numerical quality or latency claims until a reproducible evaluation produces them.

## Logging rules

- Use Loguru for structured application events.
- Log operational metadata such as event name, generated document ID, byte/page counts, timing, and stable error code.
- Never log resume text, job-description text, transcripts, candidate identifiers, file contents, API keys, or provider authorization data.

## Scope and provider control

- English is the only MVP language. Hindi is a later, separately approved milestone.
- Do not add a provider, framework, database, OCR engine, or deployment service without explaining its cost, privacy, licensing, and architectural impact when material.
- Keep provider-specific configuration at the edges of the application so the Pipecat pipeline stays readable.
- Never send a resume, job description, transcript, or API key to a provider that has not been explicitly approved for that data type.
