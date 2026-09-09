# Module 4 — English Voice Pipeline

## What we built

The Module 3 interviewer can now receive English speech in a browser and answer with speech:

```text
Browser microphone -> Deepgram STT -> Pipecat context -> Groq interviewer
                   <- Deepgram TTS <- interviewer text <-
```

Pipecat carries the audio over SmallWebRTC. Its RTVI protocol supplies browser events and live transcripts.

## Why each file exists

- `voice_services.py` creates Deepgram's streaming STT and TTS processors. Provider details stay at the edge of the application.
- `voice_pipeline.py` connects the seven application processors in the standard Pipecat order. Silero VAD, Smart Turn v3 and interruptions use Pipecat's defaults rather than custom timing logic.
- `voice_metrics.py` captures timing and usage numbers without logging interview text, documents or candidate identifiers.
- `evals/speech_quality.py` calculates WER and CER for STT only.
- `bot.py` is the runner entry point. For this module it loads only the reviewed fictional fixture. Resume upload is intentionally deferred to the client module.

## Where data goes

- Deepgram receives microphone audio and returns its transcript.
- Groq receives the grounded fixture, transcript and conversation history.
- Deepgram receives only the interviewer's reply text for speech synthesis.
- Silero VAD and Smart Turn run locally.
- Raw audio is not written to disk.

## Automated verification

From `interviewflow-ai/server`:

```powershell
.venv\Scripts\python.exe -m pytest -q tests\test_voice_services.py tests\test_voice_metrics.py tests\test_speech_quality.py tests\test_voice_pipeline.py tests\test_voice_bot.py tests\test_score_transcript_cli.py
```

These offline tests use fake processors and consume no provider credits.

## Browser smoke test

1. Put `GROQ_API_KEY` and `DEEPGRAM_API_KEY` in `interviewflow-ai/.env`.
2. From `interviewflow-ai/server`, run:

```powershell
uv run python bot.py -t webrtc
```

3. Open `http://localhost:7860/client`, allow microphone access and connect.
4. The interviewer should greet you. Try this short test:

```text
I built a Python API backed by PostgreSQL.
I chose PostgreSQL because I needed transactions and relational constraints.
Sorry, let me correct that: the main improvement came from adding an index.
I measured p95 request latency before and after the change.
I don't know that detail. Please move to another topic.
```

Speak over the interviewer during one long question. Its pending speech should stop and your answer should become the next user turn.

## Measure one STT result

Copy the exact browser transcript into `--hypothesis`:

```powershell
uv run python scripts\score_transcript.py --reference "I measured p95 request latency before and after the change" --hypothesis "PASTE THE BROWSER TRANSCRIPT HERE"
```

WER is the fraction of incorrect words. CER is the fraction of incorrect characters. Lower is better; zero means an exact transcript. One sentence is only a smoke measurement, not a publishable accuracy result.
