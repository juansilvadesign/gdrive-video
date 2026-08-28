#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "ERROR: Virtual environment Python not found at ${VENV_PYTHON}"
    echo ""
    echo "Set it up once with:"
    echo "  cd \"${SCRIPT_DIR}\""
    echo "  python3 -m venv .venv"
    echo "  .venv/bin/pip install -r requirements.txt"
    exit 1
fi

exec "${VENV_PYTHON}" "${SCRIPT_DIR}/main.py" "$@"
