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

The current public API still uses the in-memory repository. The SQLModel repositories and Alembic migrations are the persistence groundwork for a later DB-backed implementation pass.

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

The app works without credentials using deterministic local fallbacks. Copy `.env.example` to `.env` or `.env.local` and set credentials for real integrations.

pydantic-settings loads `backend/.env` and then `backend/.env.local`; real environment variables override both.

Common variables:

```bash
DATABASE_URL=sqlite:///./langbase.db
DB_ECHO=false
BROWSERBASE_API_KEY=...
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=gpt-4.1-mini
PHOENIX_ENABLED=true
PHOENIX_OTEL_ENDPOINT=http://localhost:6006/v1/traces
NAHUATL_MODEL_ENDPOINT_URL=https://your-neuron-endpoint/invoke
NAHUATL_MODEL_NAME=somosnlp-hackathon-2022/t5-small-spanish-nahuatl
```

For Supabase, use a SQLAlchemy/psycopg2 URL, for example:

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
