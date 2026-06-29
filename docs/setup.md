# Setup

## Prerequisites

- Docker Desktop with the Linux engine enabled
- Python 3.11 or newer
- Node.js 20 or newer for the dashboard
- `make`, or run the listed commands manually in PowerShell

## Configure

```powershell
Copy-Item .env.example .env
```

The demo can run without API keys:

- Missing `OPENROUTER_API_KEY` uses mock diagnosis.
- Missing `OPENAI_API_KEY` uses local hash embeddings for runbook retrieval.

For live LLM diagnosis and OpenAI embeddings, fill those keys in `.env`.

## Install Python Dependencies

```powershell
.\healer\.venv\Scripts\python.exe -m pip install -r healer\requirements.txt
```

## Run Tests

```powershell
.\healer\.venv\Scripts\python.exe -m pytest healer\tests -q
```

## Start the Stack

```powershell
docker compose -f infra\docker-compose.yml up --build
```

The healer API is available at `http://localhost:8000`.

## Start the Dashboard

```powershell
cd dashboard
npm install
npm run dev
```

The dashboard defaults to `http://localhost:3000`.

## Trigger a Demo Incident

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/demo/incident -ContentType application/json -Body '{"service":"leaky_service"}'
```
