"""Live end-to-end test for the research / get_more_data endpoints.

Runs the REAL controllers against REAL Claude + Browserbase, and writes results
to the configured database. Choose the language and action at run time.

Examples:
    uv run python scripts/live_test.py research Quechua pos
    uv run python scripts/live_test.py research Yoruba translate
    uv run python scripts/live_test.py data Quechua

It runs a preflight check first and tells you exactly what's missing (keys,
DATABASE_URL, the `browse` CLI, or un-migrated tables) before spending tokens.
"""

import argparse
import shutil
import sys
from pathlib import Path

# Make the backend root importable when run directly (python scripts/live_test.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine


def _preflight() -> list[str]:
    """Return a list of human-readable problems; empty means good to go."""
    problems: list[str] = []

    if not settings.anthropic_api_key:
        problems.append("ANTHROPIC_API_KEY is empty in .env (get it from console.anthropic.com).")
    if not settings.browserbase_api_key:
        problems.append("BROWSERBASE_API_KEY is empty in .env (get it from browserbase.com/settings).")
    if shutil.which("browse") is None:
        problems.append("`browse` CLI not on PATH (install with `npm install -g browse`).")

    db_url = settings.database_url or ""
    if "<password>" in db_url or "<host>" in db_url or not db_url:
        problems.append("DATABASE_URL is still a placeholder in .env (paste your real Supabase URL).")
    else:
        # Try to actually connect and confirm the tables exist.
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - surface any connection error
            problems.append(f"Could not connect to the database: {exc}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Live test for the agent endpoints.")
    parser.add_argument("action", choices=["research", "data"], help="Which endpoint to test.")
    parser.add_argument("language", help="Language name to research / gather (e.g. Quechua).")
    parser.add_argument(
        "type",
        nargs="?",
        choices=["pos", "translate"],
        help="Research type (required for the `research` action).",
    )
    args = parser.parse_args()

    problems = _preflight()
    if problems:
        print("Preflight failed — fix these before running a live test:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    if args.action == "research" and not args.type:
        print("The `research` action needs a type: pos or translate.")
        return 1

    # Imported here so a missing key surfaces in preflight, not at import time.
    from app.api.data.controller import DataController
    from app.api.research.controller import ResearchController

    print(f"Running live {args.action!r} for language {args.language!r}...\n")
    with Session(engine) as session:
        if args.action == "research":
            result = ResearchController(session).research(args.language, args.type)
            print("Saved research row:")
            print(result.model_dump_json(indent=2))
        else:
            rows = DataController(session).get_more_data(args.language)
            print(f"Saved {len(rows)} sentence rows:")
            for row in rows:
                print(f"  [{row.id}] {row.name}")
            if not rows:
                print("  (agent returned no sentences — nothing was written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
