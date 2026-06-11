#!/usr/bin/env bash
set -euo pipefail

# Map models to docker compose service names
# valid models: all, embed, rerank, colpali

normalized_args=()
for arg in "$@"; do
    # Replace commas with spaces, and split into array
    IFS=',' read -r -a split_args <<< "$arg"
    for part in "${split_args[@]}"; do
        # Trim whitespace
        part=$(echo "$part" | xargs)
        if [ -n "$part" ]; then
            normalized_args+=("$part")
        fi
    done
done

services=()
has_all=false
compose_files=(-f infra/models/docker-compose.yml)

case "$(uname -m)" in
    arm64|aarch64)
        if [ -f infra/models/docker-compose.arm.yml ]; then
            compose_files+=(-f infra/models/docker-compose.arm.yml)
        fi
        ;;
esac

for arg in "${normalized_args[@]}"; do
    case "$arg" in
        all)
            has_all=true
            ;;
        colpali)
            services+=("infinity-colpali")
            ;;
        *)
            echo "Error: Unknown model '$arg'." >&2
            echo "Available models: all, embed, rerank, colpali" >&2
            exit 1
            ;;
    esac
done

# If no arguments provided, or 'all' is explicitly requested
if [ "${#normalized_args[@]}" -eq 0 ] || [ "$has_all" = true ]; then
    echo "Starting all model services..."
    docker compose "${compose_files[@]}" up -d
else
    echo "Starting specified model services: ${services[*]}..."
    docker compose "${compose_files[@]}" up -d "${services[@]}"
fi
