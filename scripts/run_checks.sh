#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${PYTHON:-}" ]]; then
  :
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "ERROR: neither python3 nor python was found on PATH" >&2
  exit 1
fi

COMPILE_ONLY=false

case "${1:-}" in
  --compile-only)
    COMPILE_ONLY=true
    shift
    ;;
  "")
    ;;
  *)
    echo "usage: $0 [--compile-only]" >&2
    exit 2
    ;;
esac

if [[ "$#" -gt 0 ]]; then
  echo "usage: $0 [--compile-only]" >&2
  exit 2
fi

echo "=== Python Syntax Check ==="
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  mapfile -t python_files < <(git ls-files '*.py')
  existing_python_files=()
  for path in "${python_files[@]}"; do
    if [[ -f "$path" ]]; then
      existing_python_files+=("$path")
    fi
  done
  python_files=("${existing_python_files[@]}")
else
  mapfile -t python_files < <(
    find . -name '*.py' \
      -not -path './.git/*' \
      -not -path './.venv/*' \
      -not -path './data/*' \
      -not -path './.tmp/*' \
      -not -path './__pycache__/*' \
      -not -path './*/__pycache__/*' \
      | sort
  )
fi

if [[ "${#python_files[@]}" -eq 0 ]]; then
  echo "no Python files found" >&2
  exit 1
fi

"$PYTHON" -m py_compile "${python_files[@]}"

if [[ "$COMPILE_ONLY" == "true" ]]; then
  exit 0
fi

echo "=== Extractor Registry Check ==="
"$PYTHON" -c "from extractors import EXTRACTOR_REGISTRY; assert len(EXTRACTOR_REGISTRY) >= 10, 'Expected at least 10 extractors'; print(f'  {len(EXTRACTOR_REGISTRY)} extractors registered')"

echo "=== Prompt Registry Check ==="
"$PYTHON" scripts/prompt_registry.py

if ! "$PYTHON" scripts/build_raw_source_manifest.py --check; then
  echo "raw-source manifest is missing or stale; run: $PYTHON scripts/build_raw_source_manifest.py" >&2
  exit 1
fi

"$PYTHON" scripts/check_markdown_links.py
"$PYTHON" scripts/check_hardware_doc_structure.py
"$PYTHON" scripts/validate_exports.py --summary
"$PYTHON" scripts/validate_design_extraction.py --strict
"$PYTHON" test_regression.py
"$PYTHON" -m pytest -q
