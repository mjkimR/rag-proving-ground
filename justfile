# Print available commands
default:
    @just --list

# Initialize project modules (all, app-base, or app-tools)
init:
    uv sync

init-dev:
    uv sync --all-extras

# Run ruff format and lint for a specific module (all, app-base, or app-tools)
lint:
    uv run ruff format
    uv run ruff check --fix

# Run tests
test +paths="":
    uv run pytest

# Start backend services in CPU mode (Default / macOS). Can specify multiple profiles (e.g. just up docling marker)
up +profiles="":
    #!/usr/bin/env bash
    if [ -z "{{ profiles }}" ]; then
        docker compose -f infra/docker/docker-compose.yml up -d
    else
        profile_args=()
        for p in {{ profiles }}; do
            profile_args+=("--profile" "$p")
        done
        docker compose -f infra/docker/docker-compose.yml "${profile_args[@]}" up -d
    fi

# Start backend services in GPU mode (WSL / Linux). Can specify multiple profiles (e.g. just up-gpu docling marker)
up-gpu +profiles="":
    #!/usr/bin/env bash
    if [ -z "{{ profiles }}" ]; then
        docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.gpu.yml up --profile basic -d
    else
        profile_args=()
        for p in {{ profiles }}; do
            profile_args+=("--profile" "$p")
        done
        docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.gpu.yml "${profile_args[@]}" up -d
    fi

# Stop all backend services
down:
    docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.gpu.yml down --remove-orphans
