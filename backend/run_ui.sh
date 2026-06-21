#!/usr/bin/env bash
# Launch the Streamlit playground for the agent endpoints.
# Usage: ./run_ui.sh   (from the backend directory)
set -euo pipefail
cd "$(dirname "$0")"
exec uv run streamlit run streamlit_app.py "$@"
