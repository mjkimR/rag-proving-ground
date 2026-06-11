# AGENTS.md - Guide for AI Assistants

This repository is a **Modular RAG Experimentation and Serving Scaffold**: a monorepo for building,
evaluating, and serving Retrieval-Augmented Generation (RAG) pipelines.

- **API App**: `apps/backend` (Python, FastAPI) - parsing, chunking, knowledge-base, and worker endpoints
- **Web App**: `apps/web` (React 19, Vite, TypeScript, CopilotKit) - frontend UI
- **Core Library**: `packages/rag-core` (Python) - shared parsing, chunking, embedding, vector store, and AI utilities
- **Graph Library**: `packages/graphs` (Python, LangGraph) - LangGraph-based RAG pipeline definitions
- **Infra**: `infra/` - Orchestration configurations (`infra/services/` for resources, `infra/models/` for local models, `infra/app/` for app deployment)
- **Experiments**: `experiments/` - AutoRAG evaluation runs, baselines, and notebooks

---

## Tooling & Commands

Use **just** as the primary command runner and task orchestrator. Use **uv** for Python dependency and
environment management.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Run `just` to list the available recipes before using or documenting commands. Inspect the `justfile` when
> you need exact arguments, side effects, or implementation details. Do not rely on README files, issue
> comments, or older docs when they differ from `just`.

### Command Usage

Several recipes accept a module argument:

- `all` - backend and web
- `backend`
- `web`

Examples:

```bash
just
just init
just init backend
just lint web
just check all
just verify
just dev backend
```

Keep the `justfile` thin. If a recipe needs non-trivial shell logic, put that logic in `scripts/` and call
the script from the recipe. For finite-choice recipe arguments, prefer `just` argument attributes such as
`[arg("module", pattern="...")]` instead of duplicating validation only in shell scripts.

---

## Repository Layout

```text
rag-proving-ground/
├── apps/
│   ├── backend/                  # FastAPI application and worker
│   │   ├── app/
│   │   ├── migrations/
│   │   └── tests/
│   └── web/                      # React 19 + Vite frontend
│       └── src/
├── packages/
│   ├── rag-core/                 # Shared library: parsers, chunkers, embeddings, vector stores, config
│   │   └── src/rag_core/
│   │       ├── adapters/         # Provider adapters
│   │       ├── ai/               # LLM / reranker wrappers
│   │       ├── chunkers/         # Recursive and semantic chunking strategies
│   │       ├── embeddings/       # Embedding and indexing utilities
│   │       ├── parsers/          # Document parser schemas and renderers
│   │       └── config.py         # Pydantic settings
│   └── graphs/                   # LangGraph RAG pipeline definitions
│       └── src/rag_graphs/
├── infra/
│   ├── services/                 # Infrastructure services (Postgres, Qdrant, MinIO, Redis, Docling)
│   ├── models/                   # Model serving runtime services (Ollama, TEI)
│   └── app/                      # Application Docker orchestration placeholder
├── experiments/                  # AutoRAG configs, baselines, notebooks
├── scripts/                      # Shell helper scripts used by justfile
├── models.yaml                   # LiteLLM model routing config
├── .env.example                  # Environment variable template
├── justfile                      # Task runner SSOT
└── pyproject.toml                # uv workspace, ruff, pyright, pytest
```

---

## Architecture & Code Style

### Python Workspace (`packages/rag-core`, `packages/graphs`, `apps/backend`)

- **Package manager**: `uv`. Never use `pip install`, `poetry`, or `conda`.
- **Python version**: `>=3.13`. Use modern Python idioms where they improve clarity.
- **Type hints**: Required for public functions and class attributes. Use `just check backend` for pyright.
- **Settings**: Use `pydantic-settings` `BaseSettings` with `validation_alias` for env var names. Expose
  cached settings with `@lru_cache` factories.
- **Logging**: Use `loguru` for diagnostics. Do not use `print` in application code.
- **Database**: Use Alembic recipes from the justfile for migrations, and keep generated migration files under
  `apps/backend/migrations/versions/`.

#### Parser Adapter Pattern (`packages/rag-core/src/rag_core/adapters/parser/`)

New parser providers must follow the established adapter pattern:

- Implement the interface in `interface.py`.
- Register the implementation in `registry.py`.
- Expose it through `factory.py`.
- Resolve the active provider through `instance.py`, which reads the parser provider setting.
- Add focused unit tests under `packages/rag-core/tests/unit/test_adapters/test_parser/`.

#### Vector Store Adapter Pattern (`packages/rag-core/src/rag_core/adapters/vector_store/`)

Vector store providers follow the same interface, registry, factory, and instance pattern. Keep provider-specific
logic in `providers/` and shared lifecycle/configuration logic in the adapter package.

#### Chunkers (`packages/rag-core/src/rag_core/chunkers/`)

- `recursive.py` - LangChain `RecursiveCharacterTextSplitter`-based chunking
- `semantic.py` - semantic chunking using embedding similarity

#### LangGraph Pipelines (`packages/graphs/src/rag_graphs/`)

Define new graphs in `packages/graphs/src/rag_graphs/`. Depend on `rag-core` for shared utilities; do not
duplicate parsing, embedding, or vector-store logic.

### Backend (`apps/backend`)

- Keep API routes under feature packages in `apps/backend/app/features/**/api/`.
- Keep business flows in `usecases/`, persistence in `repos.py`, transport schemas in `schemas.py`, and database
  models in `models.py`.
- Worker entry points live under `apps/backend/app/worker/`; use `just worker` or `just dev backend` to run them.
- When backend API schemas change, run `just gen-ui-api` and include the generated web client changes.

### Frontend (`apps/web`)

- **Tech Stack**: React 19, TypeScript, Vite, CopilotKit, TanStack Query, Ant Design, generated OpenAPI client.
- **Node**: `>=24.0.0` / **npm**: `>=11.0.0` (see `.nvmrc` and `apps/web/package.json`).
- **Markdown rendering**: Use `react-markdown` + `rehype-sanitize` + `remark-gfm`. Never render raw user or LLM
  HTML without sanitization.
- **API calls**: Use the generated API client in `apps/web/src/generated/api/`. Do not add raw `fetch` calls to
  backend endpoints unless no client path exists yet.
- **Build**: Use `just check web` or `npm --prefix apps/web run build`.

---

## Testing

Pytest is configured in the workspace `pyproject.toml`.

```bash
just test
just test backend
just test-file packages/rag-core/tests/unit
just test-file apps/backend/tests
```

- `just test` runs the module-level default test set. Use `just test-file` for explicit pytest paths.
- Default empty roots are reported and skipped.
- **Framework**: `pytest` with `pytest-asyncio` (`asyncio_mode = "auto"`).
- **Mocking**: `pytest-mock`.
- **Integration**: `testcontainers[postgres]` is available for container-based integration tests.
- Add tests for new adapters, chunkers, graph nodes, backend use cases, and API behavior.

---

## Critical Constraints

1. **Security**: Never commit `.env` files, real API keys, secrets, or PII. Do not log secrets or PII.
2. **Commits**: Use concise imperative commit messages with no emojis, such as `Add Docling adapter cache layer`.
3. **Pre-flight Checks**: Before proposing a final solution, run the relevant scope of `just verify`, or the
   individual `just lint`, `just check`, `just test`, and `just test-file` recipes when narrower checks are
   more appropriate.
4. **Git Commit**: Never execute `git commit` automatically. Leave commits entirely to the user.
5. **Dependency Management**: Use `uv add` for Python dependencies and `npm --prefix apps/web install` for web
   dependencies. Do not use `pip`, `poetry`, or `conda`.
6. **Generated API Client**: After backend API/schema changes, run `just gen-ui-api` and keep generated files in
   sync.
7. **No Direct Frontend Fetch**: Use the established generated API client pattern unless a client layer does not
   exist for the endpoint yet.
