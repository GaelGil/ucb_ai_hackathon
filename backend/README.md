# LangBase Backend

FastAPI backend for a low-resource language dataset preservation MVP. It supports dataset workspaces, uploads, cached research, UPOS suggestions, OCR suggestions, review actions, a POS model training trigger, and a Spanish-to-Nahuatl translation demo adapter.

## Structure

Application code lives under `app/src`. Each API domain has a `controller.py` for FastAPI routes and a `service.py` for business logic:

```text
app/src/api/
  data/
  dataset/
  labels/
  language/
  research/
```

## Run

```bash
uv run uvicorn main:app --reload
```

The API runs on `http://127.0.0.1:8000` by default.

## Test

```bash
uv run pytest
```

## Integration Environment

The app works without credentials using deterministic local fallbacks. Copy `.env.example` to `.env` or `.env.local` and set these for real integrations:

```bash
BROWSERBASE_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
PHOENIX_ENABLED=true
PHOENIX_OTEL_ENDPOINT=http://localhost:6006/v1/traces
NAHUATL_MODEL_ENDPOINT_URL=https://your-neuron-endpoint/invoke
NAHUATL_MODEL_NAME=somosnlp-hackathon-2022/t5-small-spanish-nahuatl
```

pydantic-settings loads `backend/.env` and then `backend/.env.local`; real environment variables override both.

Database models are intentionally not implemented here. Replace `InMemoryRepository` with a DB-backed repository that preserves the same method contracts.
