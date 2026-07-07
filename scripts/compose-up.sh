#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
shift || true

case "$MODE" in
    cpu|gpu) ;;
    *)
        echo "Usage: $0 <cpu|gpu> [profiles...]" >&2
        exit 2
        ;;
esac

env_args=()
if [ -f .env ]; then
    env_args=("--env-file" ".env")
fi

compose_args=(-p rag -f infra/services/docker-compose.yml)
if [ "$MODE" = "gpu" ]; then
    compose_args+=(-f infra/services/docker-compose.gpu.yml)
fi

profile_args=()
if [ "$#" -eq 0 ]; then
    profile_args=(--profile basic)
else
    for profile in "$@"; do
        if [ "$profile" = "serve" ]; then
            if [ ! -f infra/services/docker-compose.serve.yml ]; then
                echo "Error: 'serve' profile requires infra/services/docker-compose.serve.yml, which does not exist yet." >&2
                exit 2
            fi
            compose_args+=(-f infra/services/docker-compose.serve.yml)
        fi
        profile_args+=("--profile" "$profile")
    done
fi

docker compose "${env_args[@]}" "${compose_args[@]}" "${profile_args[@]}" up -d
