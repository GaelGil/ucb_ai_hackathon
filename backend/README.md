# LangBase Backend

FastAPI backend for a low-resource language dataset preservation MVP. It supports dataset workspaces, uploads, cached research, UPOS suggestions, OCR suggestions, review actions, a POS model training trigger, and a Spanish-to-Nahuatl translation demo adapter.

## Structure

Application code lives under `app/src`. API domains own their FastAPI controllers and business services; database support lives beside them under the same source root.

```text
app/
  api.py                  # compatibility wrapper for app.src.api:create_app
  src/
    api/
      data/
      dataset/
      labels/
      language/
      research/
    database/
      models/
      repositories/
      schemas/
      session.py
    config.py
    providers.py
    tracing.py
migrations/               # Alembic migration environment and versions
```

The public API is backed by SQLModel tables and is intended to run against Supabase Postgres. Tests use in-memory SQLite only for fast isolated verification.

## Run

```bash
uv run uvicorn main:app --reload
```

The API runs on `http://127.0.0.1:8000` by default.

## Test

```bash
uv run pytest
uv run python -m compileall app main.py
```

## Environment

Copy `.env.example` to `.env` or `.env.local` and set `DATABASE_URL` before starting the API. Supabase Storage credentials are required when uploading PDFs/images to cloud storage; without them tests can still exercise the metadata path.

pydantic-settings loads `backend/.env` and then `backend/.env.local`; real environment variables override both.

Common variables:

```bash
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
DB_ECHO=false
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_STORAGE_BUCKET=langbase-uploads
BROWSERBASE_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
PHOENIX_ENABLED=true
PHOENIX_OTEL_ENDPOINT=http://localhost:6006/v1/traces
NAHUATL_MODEL_ENDPOINT_URL=https://your-neuron-endpoint/invoke
NAHUATL_MODEL_NAME=somosnlp-hackathon-2022/t5-small-spanish-nahuatl
```

For demo reliability, missing or failing external providers fall back to local demo behavior. Those fallbacks are recorded in job metadata and API warning fields so the UI can distinguish demo output from successful integrations.

Use a SQLAlchemy/psycopg2 URL from Supabase, for example:

```bash
DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
```

## Migrations

Generate a new migration after changing models in `app/src/database/models/`:

```bash
uv run alembic revision --autogenerate -m "describe your change"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Useful commands:

```bash
uv run alembic heads
uv run alembic current
uv run alembic history
uv run alembic downgrade -1
```
