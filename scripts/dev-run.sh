#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

target=$(resolve_module "${1:-all}") || exit $?

# Safely load .env file into environment variables
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "${line//[[:space:]]/}" ]]; then
            continue
        fi
        if [[ "$line" =~ ^([^=]+)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            val="${BASH_REMATCH[2]}"
            # Strip outer single/double quotes if present
            val="${val%\"}"
            val="${val#\"}"
            val="${val%\'}"
            val="${val#\'}"
            export "$key"="$val"
        fi
    done < .env
fi

PID_WEB=""
PID_BACKEND=""
PID_WORKER=""
PID_AEGRA=""

if should_run "$target" "web"; then
    path=$(resolve_module_path "web")
    echo "Starting React frontend ($path)..."
    npm --prefix "$path" run dev &
    PID_WEB=$!
fi

if should_run "$target" "backend"; then
    path=$(resolve_module_path "backend")
    echo "Starting FastAPI backend ($path)..."
    uv run --directory "$path" uvicorn app.main:create_app --port 8389 --reload &
    PID_BACKEND=$!

    echo "Starting document processing worker ($path)..."
    bash ./scripts/worker-run.sh &
    PID_WORKER=$!

    echo "Starting Aegra server..."
    # Override DATABASE_URL to target the aegra DB, and map other services to localhost
    DATABASE_URL="postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@localhost:15431/aegra" \
    POSTGRES_HOST=localhost \
    POSTGRES_PORT=15431 \
    POSTGRES_DB=aegra \
    REDIS_URL=redis://localhost:16379/0 \
    PYTHONPATH=packages/graphs/src:packages/rag-core/src \
    PORT=2026 \
    uv run aegra serve -c apps/serve/aegra.json &
    PID_AEGRA=$!
fi

# Set up clean up for processes on script termination
cleanup() {
    echo "Stopping development servers..."
    [ -n "$PID_WEB" ] && kill "$PID_WEB" 2>/dev/null || true
    [ -n "$PID_BACKEND" ] && kill "$PID_BACKEND" 2>/dev/null || true
    [ -n "$PID_WORKER" ] && kill "$PID_WORKER" 2>/dev/null || true
    [ -n "$PID_AEGRA" ] && kill "$PID_AEGRA" 2>/dev/null || true
}

PIDS=()
[ -n "$PID_WEB" ] && PIDS+=("$PID_WEB")
[ -n "$PID_BACKEND" ] && PIDS+=("$PID_BACKEND")
[ -n "$PID_WORKER" ] && PIDS+=("$PID_WORKER")
[ -n "$PID_AEGRA" ] && PIDS+=("$PID_AEGRA")

is_job_running() {
    local wanted_pid="$1"
    local running_pid

    for running_pid in $(jobs -pr); do
        if [ "$running_pid" = "$wanted_pid" ]; then
            return 0
        fi
    done

    return 1
}

if [ ${#PIDS[@]} -ne 0 ]; then
    trap cleanup SIGINT SIGTERM EXIT

    while true; do
        for pid in "${PIDS[@]}"; do
            if ! is_job_running "$pid"; then
                set +e
                wait "$pid"
                stopped_status=$?
                set -e
                echo "Background component $pid stopped with status $stopped_status. Shutting down remaining servers..."
                exit "$stopped_status"
            fi
        done
        sleep 1
    done
fi
