# Module 8 — persistence and Render deployment

## What

Module 8 keeps the existing interview pipeline and adds two environment-specific edges:

- Local development uses SmallWebRTC and SQLite.
- Render uses Daily WebRTC and a PostgreSQL database such as Neon.

The React client and Python pipeline are otherwise the same application.

## Why

SmallWebRTC is convenient on one computer, but hosted browser audio needs a production WebRTC service. Daily creates the room and carries the live audio. SQLite is durable on a local disk, while Render's free filesystem is temporary, so the deployed app uses PostgreSQL for one-use setup data and final scorecards.

The raw PDF and audio are not stored. Extracted setup text expires after one hour and is deleted as soon as the call claims it. A final scorecard expires after seven days.

## How

1. `render.yaml` creates a static React site and a Docker web service.
2. React selects Daily using `VITE_VOICE_TRANSPORT=daily` and asks Pipecat's `/start` endpoint to create a room.
3. Pipecat creates a short-lived Daily room and starts the same cascaded interview pipeline.
4. `DATABASE_URL` selects PostgreSQL; without it, the backend selects SQLite.
5. `/health` checks that the process responds. `/ready` also checks the configured database.
6. The browser sends a small health request once per minute during an active interview so a free Render service does not idle during Daily's separate media connection.

## Secret flow

Render prompts for these values because they are marked `sync: false`:

- `GROQ_API_KEY`
- `DEEPGRAM_API_KEY`
- `DAILY_API_KEY`
- `DATABASE_URL`

The values stay in Render's secret store and are never committed.

## Verify locally

Backend:

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai\server
uv sync --all-groups
uv run pytest -q
```

Frontend:

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai\client
npm.cmd test
npm.cmd run build
```

Container, when Docker Desktop is running:

```powershell
cd C:\Users\mrina\Desktop\Voice_ai\interviewflow-ai
docker build -f server/Dockerfile server
```

## Deploy

Push the repository to GitHub, open Render's **New Blueprint** page, select the repository, and use the root `render.yaml`. Enter the four secret values when prompted. After both services are live, verify `/health`, `/ready`, resume setup, one complete Daily call, and scorecard retrieval.

The free backend can cold-start after being idle and is appropriate for a portfolio MVP, not a production SLA. Its small CPU/RAM allocation also means we should verify one interview at a time before claiming concurrency.
