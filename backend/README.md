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
# Backend — Database Layer

SQLModel + Alembic + Pydantic Settings against Supabase Postgres.

## Structure

```
app/
├── core/
│   ├── config.py          # Pydantic Settings (loads .env -> DATABASE_URL)
│   └── database.py         # SQLAlchemy engine + get_session()
├── database/
│   ├── models/             # SQLModel tables: Language, Data, Label
│   ├── schemas/            # Pydantic request/response models
│   └── repositories/       # Data-access layer (one class per table)
└── api/
    └── language/           # controller.py + service.py (example resource)
migrations/                 # Alembic (env.py wired to Settings + SQLModel.metadata)
└── versions/               # Migration files
```

### Data model
- **Language** (id, name) → has many **Data**
- **Data** (id, name, type ∈ {text, image, audio}) → belongs to Language, has many **Labels**
- **Label** (id, name, type, value) → belongs to Data

## Setup

1. Copy the env template and fill in your Supabase connection string:
   ```bash
   cp .env.example .env
   ```
   In Supabase: **Project Settings → Database → Connection string → URI**.
   Use the direct/session connection (port `5432`), change the scheme to
   `postgresql+psycopg2://`, and append `?sslmode=require`:
   ```
   DATABASE_URL=postgresql+psycopg2://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```

2. Install dependencies (already done if `uv.lock` exists):
   ```bash
   uv sync
   ```

## Migrations

Generate a new migration after changing models in `app/database/models/`:
```bash
uv run alembic revision --autogenerate -m "describe your change"
```

Apply migrations to the database:
```bash
uv run alembic upgrade head
```

Other useful commands:
```bash
uv run alembic current        # show current revision
uv run alembic history        # list migrations
uv run alembic downgrade -1   # roll back one migration
```
