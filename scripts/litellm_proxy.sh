#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env}"
CONFIG_FILE="${CONFIG_FILE:-$ROOT_DIR/models.yaml}"
PORT="${LITELLM_PORT:-4000}"
STATE_DIR="$ROOT_DIR/.integrations/litellm"
PID_FILE="$STATE_DIR/litellm-${PORT}.pid"
LOG_FILE="$STATE_DIR/litellm-${PORT}.log"

mkdir -p "$STATE_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing LiteLLM config: $CONFIG_FILE" >&2
  echo "Create it from models.example.yaml or set CONFIG_FILE=/path/to/models.yaml" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  echo "Missing env file: $ENV_FILE" >&2
  echo "Create .env from .env.example or set ENV_FILE=/path/to/.env" >&2
  exit 1
fi

if command -v litellm >/dev/null 2>&1; then
  LITELLM_CMD=(litellm)
elif [[ -x "$ROOT_DIR/.venv/bin/litellm" ]]; then
  LITELLM_CMD=("$ROOT_DIR/.venv/bin/litellm")
else
  echo "Could not find litellm executable." >&2
  echo "Install dependencies first, for example: uv sync" >&2
  exit 1
fi

missing_env=()
while IFS= read -r var_name; do
  if [[ -n "$var_name" && -z "${!var_name:-}" ]]; then
    missing_env+=("$var_name")
  fi
done < <(grep -Eho 'os\.environ/[A-Za-z_][A-Za-z0-9_]*' "$CONFIG_FILE" | sed 's#os.environ/##' | sort -u)

if [[ ${#missing_env[@]} -gt 0 ]]; then
  echo "Missing required environment variables from $ENV_FILE:" >&2
  printf '  %s\n' "${missing_env[@]}" >&2
  exit 1
fi

stop_existing() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "Stopping existing LiteLLM proxy pid=$pid"
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

echo "Starting LiteLLM proxy on port $PORT"
echo "Config: $CONFIG_FILE"
echo "Env: $ENV_FILE"
echo "Log: $LOG_FILE"

cd "$ROOT_DIR"
nohup "${LITELLM_CMD[@]}" --config "$CONFIG_FILE" --port "$PORT" >"$LOG_FILE" 2>&1 &
echo "$!" > "$PID_FILE"

echo "LiteLLM proxy started pid=$(cat "$PID_FILE")"
echo "Base URL: http://localhost:$PORT"
