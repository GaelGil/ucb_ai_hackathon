"""Simulated end-to-end test — no API keys or Postgres required.

Runs the REAL controllers, services, repositories, and persistence against an
in-memory SQLite database, but STUBS the agent's web output. This lets you see
the exact shape the app returns without spending tokens or connecting keys.

Only the agent's results are placeholder — the flow, structure, and saved rows
are identical to a live run. In production, the stub is replaced by real
Claude + Browserbase output.

Examples:
    uv run python scripts/simulated_test.py data Quechua
    uv run python scripts/simulated_test.py research Quechua pos
"""

import argparse
import sys
from pathlib import Path

# Make the backend root importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.database.models  # noqa: F401 — registers all tables on the metadata


# --- Stubbed agent output (stands in for Claude + Browserbase) ---------------

def _fake_sentences(language_name: str) -> list[str]:
    return [
        f"[{language_name}] Ñuqaqa simita rimani.",
        f"[{language_name}] Wasiyman rini paqarin.",
        f"[{language_name}] Allillanchu kashanki?",
        f"[{language_name}] Inti lluqsimun urqukunamanta.",
    ]


def _fake_notes(language_name: str, research_type: str) -> str:
    return (
        f"[SIMULATED notes] Found 4 web sources on {research_type} for "
        f"{language_name}. Example finding: a small annotated corpus exists "
        "(source: https://example.org/corpus)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulated end-to-end endpoint test.")
    parser.add_argument("action", choices=["research", "data"])
    parser.add_argument("language", help="Language name (e.g. Quechua).")
    parser.add_argument("type", nargs="?", choices=["pos", "translate"])
    args = parser.parse_args()

    if args.action == "research" and not args.type:
        print("The `research` action needs a type: pos or translate.")
        return 1

    # In-memory DB built from the real models.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Swap the agent calls for stubs (the only non-real part).
    import app.api.data.service as data_svc
    import app.api.research.service as research_svc

    data_svc.run_get_more_data = _fake_sentences
    research_svc.run_research_agent = lambda name, type: _fake_notes(name, type)

    from app.api.data.controller import DataController
    from app.api.research.controller import ResearchController

    print(f">>> USER REQUEST: {args.action}(language={args.language!r}"
          + (f", type={args.type!r}" if args.type else "") + ")")
    print("    (SIMULATED — agent output is placeholder; everything else is real)\n")

    with Session(engine) as session:
        if args.action == "research":
            result = ResearchController(session).research(args.language, args.type)
            print("<<< APP RETURNS (saved research row):")
            print(result.model_dump_json(indent=2))
        else:
            from app.database.models.data import Data

            rows = DataController(session).get_more_data(args.language)
            print(f"<<< APP RETURNS {len(rows)} sentence rows:\n")
            for row in rows:
                print("   ", row.model_dump_json())

            saved = session.exec(select(Data)).all()
            if saved:
                print(
                    f"\n--- persisted: {len(saved)} Data rows, "
                    f"language_id={saved[0].language_id}, "
                    f"dataset_id={saved[0].dataset_id} (one shared dataset) ---"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
