#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_STREAMLIT="${SCRIPT_DIR}/.venv/bin/streamlit"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_STREAMLIT}" && ! -x "${VENV_PYTHON}" ]]; then
    echo "ERROR: Virtual environment Python/Streamlit not found at ${SCRIPT_DIR}/.venv"
    echo ""
    echo "Set it up once with:"
    echo "  cd \"${SCRIPT_DIR}\""
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements-streamlit.txt"
    exit 1
fi

echo "WARNING: This is a legacy local preview/install surface."
echo "Use run.sh / run.bat for private, large, resumable, or integrity-sensitive transfers."
if [[ -x "${VENV_STREAMLIT}" ]]; then
    exec "${VENV_STREAMLIT}" run "${SCRIPT_DIR}/streamlit.py" --logger.level=error "$@"
else
    exec "${VENV_PYTHON}" -m streamlit run "${SCRIPT_DIR}/streamlit.py" --logger.level=error "$@"
fi
