"""Streamlit playground for the research / get_more_data agent endpoints.

Run it from the backend directory:

    uv run streamlit run streamlit_app.py

Modes:
  * Simulated  — stubs the agent; play with the UI without any keys.
  * Live       — calls the real Claude + Browserbase agents (needs API keys).

Optionally saves results to the configured database (needs a real DATABASE_URL
and `alembic upgrade head`).
"""

import shutil
import sys
from pathlib import Path

# Make the backend root importable when launched via `streamlit run`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from app.core.config import settings

st.set_page_config(page_title="Language Agent Playground", page_icon="🌍", layout="wide")


# --- Status helpers -----------------------------------------------------------

def _db_is_real() -> bool:
    db = settings.database_url or ""
    return bool(db) and "<password>" not in db and "<host>" not in db


def _db_reachable() -> tuple[bool, str]:
    if not _db_is_real():
        return False, "DATABASE_URL is a placeholder"
    try:
        from sqlalchemy import text

        from app.core.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:80]


# --- Simulated stubs ----------------------------------------------------------

def _sim_research(language: str, rtype: str) -> str:
    return (
        f"### Simulated research notes — {rtype} for {language}\n\n"
        "- **Datasets:** a small annotated corpus (source: https://example.org/corpus)\n"
        "- **Tools:** one tagger prototype (source: https://example.org/tagger)\n"
        "- **Papers:** 2 workshop papers since 2021\n\n"
        "_This is placeholder output. Switch to Live mode with API keys for real results._"
    )


def _sim_sentences(language: str) -> list[str]:
    return [
        f"{language} example sentence one.",
        f"{language} example sentence two.",
        f"{language} example sentence three.",
        f"{language} example sentence four.",
    ]


# --- Sidebar: status + mode ---------------------------------------------------

st.sidebar.header("Connection status")

anthropic_ok = bool(settings.anthropic_api_key)
browserbase_ok = bool(settings.browserbase_api_key)
cli_ok = shutil.which("browse") is not None
db_ok, db_msg = _db_reachable()

st.sidebar.write(f"{'✅' if anthropic_ok else '❌'} ANTHROPIC_API_KEY")
st.sidebar.write(f"{'✅' if browserbase_ok else '❌'} BROWSERBASE_API_KEY")
st.sidebar.write(f"{'✅' if cli_ok else '❌'} `browse` CLI")
st.sidebar.write(f"{'✅' if db_ok else '❌'} Database ({db_msg})")

live_ready = anthropic_ok and browserbase_ok and cli_ok

st.sidebar.divider()
default_mode = "Live" if live_ready else "Simulated"
mode = st.sidebar.radio(
    "Mode",
    ["Simulated", "Live"],
    index=0 if default_mode == "Simulated" else 1,
    help="Simulated stubs the agent. Live calls real Claude + Browserbase.",
)
if mode == "Live" and not live_ready:
    st.sidebar.warning("Live needs both API keys and the `browse` CLI. Fill them in .env.")

save_to_db = st.sidebar.checkbox(
    "Save results to database",
    value=False,
    disabled=not db_ok,
    help="Persist via the real controllers. Requires a reachable database.",
)


# --- Main UI ------------------------------------------------------------------

st.title("🌍 Language Agent Playground")
st.caption(
    "Test the **research** and **get_more_data** endpoints. "
    f"Current mode: **{mode}**" + (" · saving to DB" if save_to_db else "")
)

tab_research, tab_data = st.tabs(["🔎 Research", "📝 Get more data (sentences)"])


def _count(session, model, language_id) -> int:
    from sqlmodel import func, select

    return session.exec(
        select(func.count()).select_from(model).where(model.language_id == language_id)
    ).one()


def _run_research(language: str, rtype: str):
    if mode == "Simulated":
        return {"notes": _sim_research(language, rtype), "saved": None, "total": None}
    if save_to_db:
        from sqlmodel import Session

        from app.api.research.controller import ResearchController
        from app.core.database import engine
        from app.database.models.research import Research

        with Session(engine) as session:
            row = ResearchController(session).research(language, rtype)
            total = _count(session, Research, row.language_id)
        return {"notes": row.notes, "saved": row.model_dump(), "total": total}
    from app.agents import run_research

    return {"notes": run_research(language, rtype), "saved": None, "total": None}


def _run_data(language: str):
    if mode == "Simulated":
        return {"sentences": _sim_sentences(language), "saved": None, "total": None}
    if save_to_db:
        from sqlmodel import Session

        from app.api.data.controller import DataController
        from app.core.database import engine
        from app.database.models.data import Data

        with Session(engine) as session:
            rows = DataController(session).get_more_data(language)
            total = _count(session, Data, rows[0].language_id) if rows else 0
        return {
            "sentences": [r.name for r in rows],
            "saved": [r.model_dump() for r in rows],
            "total": total,
        }
    from app.agents import run_get_more_data

    return {"sentences": run_get_more_data(language), "saved": None, "total": None}


with tab_research:
    st.subheader("Research a language")
    col1, col2 = st.columns([3, 2])
    r_language = col1.text_input("Language name", value="Quechua", key="r_lang")
    r_type = col2.selectbox("Type", ["pos", "translate"], key="r_type")
    if st.button("Run research", type="primary", key="r_btn"):
        if not r_language.strip():
            st.error("Enter a language name.")
        else:
            with st.spinner(f"Researching {r_type} for {r_language}..."):
                try:
                    out = _run_research(r_language.strip(), r_type)
                    st.success("Done.")
                    st.markdown(out["notes"] or "_(no notes returned)_")
                    if out["saved"]:
                        if out["total"] is not None:
                            st.metric(
                                f"Total research rows for {r_language} in DB",
                                out["total"],
                            )
                        st.caption("Saved row:")
                        st.json(out["saved"])
                except Exception as exc:  # noqa: BLE001
                    st.error(f"{type(exc).__name__}: {exc}")


with tab_data:
    st.subheader("Gather sentences in a language")
    d_language = st.text_input("Language name", value="Quechua", key="d_lang")
    if st.button("Get more data", type="primary", key="d_btn"):
        if not d_language.strip():
            st.error("Enter a language name.")
        else:
            with st.spinner(f"Gathering sentences in {d_language}..."):
                try:
                    out = _run_data(d_language.strip())
                    sentences = out["sentences"]
                    st.success(f"Got {len(sentences)} sentence(s).")
                    if sentences:
                        st.table({"sentence": sentences})
                    else:
                        st.info("The agent returned no sentences — nothing was saved.")
                    if out["saved"]:
                        if out["total"] is not None:
                            st.metric(
                                f"Total sentence rows for {d_language} in DB",
                                out["total"],
                            )
                        st.caption("Saved rows:")
                        st.json(out["saved"])
                except Exception as exc:  # noqa: BLE001
                    st.error(f"{type(exc).__name__}: {exc}")
