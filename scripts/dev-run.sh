#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

target=$(resolve_module "${1:-all}")

PID_WEB=""
PID_BACKEND=""

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
fi

# Set up clean up for processes on script termination
cleanup() {
    echo "Stopping development servers..."
    [ -n "$PID_WEB" ] && kill "$PID_WEB" 2>/dev/null || true
    [ -n "$PID_BACKEND" ] && kill "$PID_BACKEND" 2>/dev/null || true
}

PIDS=()
[ -n "$PID_WEB" ] && PIDS+=("$PID_WEB")
[ -n "$PID_BACKEND" ] && PIDS+=("$PID_BACKEND")

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
