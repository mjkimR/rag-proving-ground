#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/services/docling"
PORT="${DOCLING_SERVE_PORT:-5001}"
HOST="${DOCLING_SERVE_HOST:-127.0.0.1}"
STATE_DIR="$ROOT_DIR/.integrations/docling"
PID_FILE="$STATE_DIR/docling-${PORT}.pid"
LOG_FILE="$STATE_DIR/docling-${PORT}.log"
ENABLE_UI="${DOCLING_SERVE_ENABLE_UI:-1}"
LOAD_MODELS_AT_BOOT="${DOCLING_SERVE_LOAD_MODELS_AT_BOOT:-0}"
MAX_SYNC_WAIT="${DOCLING_SERVE_MAX_SYNC_WAIT:-120}"
DOCLING_DEVICE="${DOCLING_DEVICE:-cpu}"
PYTORCH_ENABLE_MPS_FALLBACK="${PYTORCH_ENABLE_MPS_FALLBACK:-1}"

mkdir -p "$STATE_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "Could not find uv executable." >&2
  echo "Install uv first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if [[ ! -f "$SERVICE_DIR/pyproject.toml" ]]; then
  echo "Missing Docling service project: $SERVICE_DIR/pyproject.toml" >&2
  exit 1
fi

stop_existing() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Stopping existing Docling Serve pid=$pid"
      kill "$pid"
      for _ in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null; then
          break
        fi
        sleep 0.2
      done
      if kill -0 "$pid" 2>/dev/null; then
        echo "Existing process did not stop cleanly; forcing pid=$pid"
        kill -9 "$pid"
      fi
    fi
    rm -f "$PID_FILE"
  fi

  if [[ "${FORCE_PORT_KILL:-0}" == "1" ]] && command -v lsof >/dev/null 2>&1; then
    local port_pids
    port_pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$port_pids" ]]; then
      echo "Stopping process listening on port $PORT: $port_pids"
      kill $port_pids 2>/dev/null || true
      sleep 0.5
    fi
  fi
}

stop_existing

if command -v lsof >/dev/null 2>&1 && lsof -tiTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use and was not started by this script." >&2
  echo "Stop that process first, or rerun with FORCE_PORT_KILL=1 if you are sure." >&2
  exit 1
fi

export UVICORN_HOST="$HOST"
export UVICORN_PORT="$PORT"
export DOCLING_SERVE_ENABLE_UI="$ENABLE_UI"
export DOCLING_SERVE_LOAD_MODELS_AT_BOOT="$LOAD_MODELS_AT_BOOT"
export DOCLING_SERVE_MAX_SYNC_WAIT="$MAX_SYNC_WAIT"
export DOCLING_DEVICE
export PYTORCH_ENABLE_MPS_FALLBACK

if [[ -n "${DOCLING_SERVE_ARTIFACTS_PATH:-}" ]]; then
  mkdir -p "$DOCLING_SERVE_ARTIFACTS_PATH"
  export DOCLING_SERVE_ARTIFACTS_PATH
fi

echo "Starting Docling Serve on http://$HOST:$PORT"
echo "Service project: $SERVICE_DIR"
echo "Docling device: $DOCLING_DEVICE"
echo "PyTorch MPS fallback: $PYTORCH_ENABLE_MPS_FALLBACK"
if [[ -n "${DOCLING_SERVE_ARTIFACTS_PATH:-}" ]]; then
  echo "Artifacts: $DOCLING_SERVE_ARTIFACTS_PATH"
fi
echo "Log: $LOG_FILE"

cd "$SERVICE_DIR"
nohup uv run docling-serve run >"$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"

echo "Docling Serve started pid=$(cat "$PID_FILE")"
echo "API docs: http://$HOST:$PORT/docs"
if [[ "$ENABLE_UI" == "1" || "$ENABLE_UI" == "true" || "$ENABLE_UI" == "True" ]]; then
  echo "UI: http://$HOST:$PORT/ui"
fi
