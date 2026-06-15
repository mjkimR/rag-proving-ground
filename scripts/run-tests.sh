#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

PATHS=("$@")
DEFAULT_TEST_PATHS=(
    "packages/rag-core/tests"
    "packages/graphs/tests"
    "packages/rag-eval/tests"
    "apps/backend/tests"
)

# Default pytest options for a cleaner output
DEFAULT_PYTEST_OPTIONS="-q --tb=short --disable-warnings --no-header"
PYTEST_OPTIONS="${PYTEST_OPTIONS:-$DEFAULT_PYTEST_OPTIONS}"
PROGRESS_LINE_FILTER='^[\.sFxFw]*\s+\[.*\]$'

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
status=0
allow_empty=0

if [ ${#PATHS[@]} -eq 0 ]; then
    PATHS=("${DEFAULT_TEST_PATHS[@]}")
    allow_empty=1
fi

for path in "${PATHS[@]}"; do
    echo "Running pytest: $path"
    test_status=0
    uv run pytest $PYTEST_OPTIONS "$path" >"$tmp" 2>&1 || test_status=$?
    grep -vE "$PROGRESS_LINE_FILTER" "$tmp" || true

    if [ "$test_status" -eq 5 ] && [ "$allow_empty" -eq 1 ]; then
        echo "No tests collected for $path."
        continue
    fi

    if [ "$test_status" -ne 0 ]; then
        status="$test_status"
    fi
done

exit "$status"
