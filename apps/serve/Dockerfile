FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
COPY apps/backend/pyproject.toml apps/backend/pyproject.toml
COPY packages/graphs/pyproject.toml packages/graphs/pyproject.toml
COPY packages/rag-core/pyproject.toml packages/rag-core/pyproject.toml

COPY apps/serve apps/serve
COPY packages/graphs/src packages/graphs/src
COPY packages/rag-core/src packages/rag-core/src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    AEGRA_CONFIG=/app/apps/serve/aegra.json \
    PYTHONPATH=/app/packages/graphs/src:/app/packages/rag-core/src

EXPOSE 2026

CMD ["aegra", "serve", "-c", "/app/apps/serve/aegra.json"]
