#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_CMD=("$PYTHON_BIN" -m pip)

"${PIP_CMD[@]}" install --upgrade pip
"${PIP_CMD[@]}" install -r requirements-dev.txt

echo
echo "Bootstrap complete."
echo "Next steps:"
echo "  export GEMINI_API_KEY='<your-api-key>'"
echo "  ./scripts/run_checks.sh"
