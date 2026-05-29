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
