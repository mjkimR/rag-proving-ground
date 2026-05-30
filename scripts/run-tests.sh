#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

PATHS=("$@")

# Default pytest options for a cleaner output
DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"
PROGRESS_LINE_FILTER='^[\.sFxFw]*\s+\[.*\]$'

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
status=0

# If paths are empty, run the default unit tests
if [ ${#PATHS[@]} -eq 0 ]; then
    PATHS=("packages/rag-core/src/tests")
fi

uv run pytest $PYTEST_OPTIONS "${PATHS[@]}" >"$tmp" 2>&1 || status=$?
grep -vE "$PROGRESS_LINE_FILTER" "$tmp" || true
exit "$status"
