# AGENTS.md - Guide for AI Assistants

This repository is a **Modular RAG Experimentation and Serving Scaffold** — a monorepo for building,
evaluating, and serving Retrieval-Augmented Generation (RAG) pipelines.

- **API App**: `apps/api` (Python, FastAPI) — parsing and chunking REST endpoints
- **Web App**: `apps/web` (React 19, Vite, TypeScript, CopilotKit) — frontend UI
- **Core Library**: `packages/rag-core` (Python) — shared parsing, chunking, embedding, and AI utilities
- **Graph Library**: `packages/graphs` (Python, LangGraph) — LangGraph-based RAG pipeline definitions
- **Infra**: `infra/docker/` — Docker Compose services (LiteLLM, MinIO, Docling)
- **Experiments**: `experiments/` — AutoRAG evaluation runs, baselines, and notebooks

---

## Tooling & Commands

We use **just** as the primary command runner and task orchestrator, and **uv** as the Python package manager.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Do NOT rely on hardcoded arguments in documentation. Always read the `justfile` directly to inspect
> available targets, parameter defaults, and task implementation scripts.

### Scripts & Shared Infrastructure

- **Separation of Concerns**: Avoid writing complex bash commands inline in `justfile` recipes. Delegate
  execution logic to dedicated shell scripts inside the `scripts/` directory to keep the `justfile` as a
  thin orchestration layer.

### Quick Command Reference

- `just init`: Install all dependencies (`uv sync`)
- `just init-dev`: Install all dependencies including dev extras (`uv sync --all-extras`)
- `just lint`: Format and lint all Python code with `ruff`
- `just test`: Run the full test suite with `pytest`
- `just up`: Start infrastructure in CPU mode (default profile: `basic`)
- `just up docling marker`: Start with additional profiles
- `just up-gpu`: Start infrastructure in GPU mode (WSL/Linux)
- `just down`: Stop all running Docker services

---

## Repository Layout

```
rag-proving-ground/
├── apps/
│   ├── api/                      # FastAPI application (parsing/chunking endpoints)
│   │   └── app/main.py
│   └── web/                      # React 19 + Vite frontend
│       └── src/
├── packages/
│   ├── rag-core/                 # Shared library: parsers, chunkers, embeddings, AI, config
│   │   └── src/rag_core/
│   │       ├── adapters/         # Provider adapters (e.g., Docling parser adapter)
│   │       ├── ai/               # LLM / reranker wrappers
│   │       ├── chunkers/         # Recursive and semantic chunking strategies
│   │       ├── embeddings/       # Embedding model wrappers
│   │       ├── parsers/          # Document parser interfaces and schemas
│   │       ├── vector_db/        # Vector store utilities
│   │       └── config.py         # Pydantic settings (LiteLLM, Parser, HTTP)
│   └── graphs/                   # LangGraph RAG pipeline definitions
│       └── src/rag_graphs/
├── infra/
│   └── docker/
│       ├── docker-compose.yml
│       └── docker-compose.gpu.yml
├── experiments/
│   ├── autorag/                  # AutoRAG evaluation configs and results
│   ├── baselines/                # Baseline pipeline scripts
│   └── notebooks/                # Jupyter notebooks
├── scripts/                      # Shell helper scripts (litellm_proxy, docling_serve, etc.)
├── models.yaml                   # LiteLLM model routing config
├── .env.example                  # Environment variable template
├── justfile                      # Task runner (SSOT for all commands)
└── pyproject.toml                # Workspace root (uv workspace, ruff, pyright, pytest)
```

---

## Architecture & Code Style

### Python Workspace (`packages/rag-core`, `packages/graphs`, `apps/api`)

- **Package manager**: `uv`. Never use `pip install` directly. Use `uv add` to add dependencies.
- **Python version**: `>=3.13`. Use modern Python idioms (`match`, `type X = ...`, etc.).
- **Type hints**: Mandatory on all public functions and class attributes. Run `uv run pyright` to check.
- **Settings**: Use `pydantic-settings` `BaseSettings` with `validation_alias` for env var names. Expose
  settings via `@lru_cache` factory functions (see `packages/rag-core/src/rag_core/config.py`).
- **Logging**: Use `loguru` (already a dependency of `rag-core`). Never use `print` for diagnostics.

#### Parser Adapter Pattern (`packages/rag-core/src/rag_core/adapters/parser/`)

New parser providers must follow the established adapter pattern:

- Implement the interface defined in `interface.py`
- Register the implementation in `registry.py`
- Expose it via the factory in `factory.py`
- Resolve the active provider through `instance.py` (reads `PARSER_PROVIDER` env var)

#### Chunkers (`packages/rag-core/src/rag_core/chunkers/`)

- `recursive.py` — LangChain `RecursiveCharacterTextSplitter`-based chunking
- `semantic.py` — Semantic chunking using embedding similarity

#### LangGraph Pipelines (`packages/graphs/src/rag_graphs/`)

- Define new graphs in `packages/graphs/src/rag_graphs/`.
- Depend on `rag-core` for shared utilities; do not duplicate parsing or embedding logic.

### Frontend (`apps/web`)

- **Tech Stack**: React 19, TypeScript, Vite, CopilotKit (`@copilotkit/react-core`, `@copilotkit/react-ui`)
- **Node**: `>=24.0.0` / **npm**: `>=11.0.0` (see `.nvmrc` and `engines` in `package.json`)
- **Markdown rendering**: Use `react-markdown` + `rehype-sanitize` + `remark-gfm`. Never render raw HTML
  from user or LLM content without sanitization.
- **Dev server**: `npm run dev` (bound to `127.0.0.1`)
- **Build**: `npm run build` (runs `tsc --noEmit` then Vite build)

---

## Testing

Tests live in `packages/rag-core/src/tests/` and are configured in the workspace `pyproject.toml`.

```bash
just test  # Run all tests
uv run pytest packages/rag-core/src/tests/unit  # Run unit tests only
```

- **Framework**: `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`)
- **Mocking**: `pytest-mock`
- **Integration**: `testcontainers[postgres]` for container-based integration tests
- Always add tests for new adapters, chunkers, and graph nodes.

---

## Critical Constraints

1. **Security**: NEVER commit `.env` files or real API keys. The `.gitignore` already excludes `.env`.
   NEVER log secrets or PII.
2. **Commits**: Concise, imperative, no emojis (e.g., `Add Docling adapter cache layer`).
3. **Pre-flight Checks**: Always run `just lint` and `just test` before proposing a final solution.
4. **Git Commit**: NEVER execute `git commit` commands automatically. Commits must be left entirely to the user.
5. **uv only**: Do not invoke `pip`, `poetry`, or `conda`. All dependency management goes through `uv`.
6. **No direct `fetch`**: On the frontend, use the established API client pattern; do not call backend
   endpoints with raw `fetch` unless no SDK/client layer exists yet.
