# Module 7 — React client

## What

The client has three screens: interview setup, live interview, and scorecard. Setup validates the resume and freezes the displayed rubric before microphone access. The live screen carries real SmallWebRTC audio, renders Pipecat's conversation stream, and displays the server timer. The final screen polls the completed Module 6 scorecard.

## Why

Pipecat handles the real-time media session, but it does not know our application inputs or scorecard layout. This thin client layer connects the existing modules without putting PDF extraction or evaluation inside the latency-sensitive audio pipeline.

## How data moves

1. React sends the PDF, job description, and approved rubric to `/api/interview-setup`.
2. Python validates and extracts the PDF in memory, then returns a one-use `setup_id`.
3. Pipecat's `/start` request carries only that ID. Resume contents do not appear in the runner request log.
4. Pipecat React hooks show connection, microphone, speaking, and transcript state.
5. RTVI server messages synchronize the monotonic interview timer.
6. Ending the call starts Module 6 evaluation; React polls `/api/interview-results/{session_id}` until the scorecard is ready.

## Run locally

Terminal 1:

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai\server
uv run python bot.py -t webrtc
```

Terminal 2:

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai\client
npm.cmd run dev
```

Open `http://localhost:5173`. The runner's `/client` URL is only Pipecat's generic development client.

## Verification

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai\client
npm.cmd test
npm.cmd run build
```

Setup and result storage are process-local for the MVP and disappear when the server restarts. Durable transcript/scorecard storage remains a Module 8 decision.
