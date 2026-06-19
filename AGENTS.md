# AGENTS.md - Guide for AI Assistants

This repository is a **Modular RAG Experimentation and Serving Scaffold**: a monorepo for building, evaluating, and serving Retrieval-Augmented Generation (RAG) pipelines.

---

## Tooling & Commands

Use **just** as the primary command runner and task orchestrator. Use **uv** for Python dependency and environment management.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Run `just` to list the available recipes before using or documenting commands. Inspect the `justfile` when
> you need exact arguments, side effects, or implementation details. Do not rely on README files, issue
> comments, or older docs when they differ from `just`.

Most module-scoped recipes accept `all`, `backend`, or `web`. Common recipes include `just init`, `just lint`, `just check`, `just test`, `just verify`, and `just dev backend`.

Keep the `justfile` thin. If a recipe needs non-trivial shell logic, put that logic in `scripts/` and call the script from the recipe. For finite-choice recipe arguments, prefer `just` argument attributes such as `[arg("module", pattern="...")]` instead of duplicating validation only in shell scripts.

---

## Workspace Map

- `apps/backend` - Python FastAPI API and FastStream worker. Feature code lives under `app/features`; worker orchestration lives under `app/worker`.
- `apps/web` - React 19, Vite, TypeScript, CopilotKit UI. Use the generated OpenAPI client under `src/generated/api`.
- `packages/rag-core` - shared RAG primitives: parsing, chunking, retrieval, embedding, generation, guardrails, adapters, and config.
- `packages/graphs` - LangGraph RAG pipeline definitions that depend on `rag-core`.
- `packages/rag-eval` - shared evaluation interfaces and runners for RAGAS, DeepEval, and related evaluation flows.
- `infra/services` - stateful/backend services such as Postgres, Qdrant, MinIO, Redis, and Docling.
- `infra/models` - local model-serving runtimes such as Ollama and TEI.
- `infra/app` - application Docker orchestration placeholder.
- `experiments` and `datasets` - AutoRAG evaluation runs, baselines, notebooks, and local/cached data.
- `scripts` - shell helpers called by the `justfile`; keep non-trivial recipe logic here.

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
- **Local config**: `.env` and `models.yaml` are gitignored local runtime configuration files. They may be read
  when needed for local diagnosis, but never copy their contents into docs, logs, commits, generated fixtures, or
  final responses. Prefer `.env.example` and `models.example.yaml` when documenting configuration.

#### Adapter Patterns

Parser and vector-store providers follow the adapter pattern: `interface.py`, `registry.py`, `factory.py`, `instance.py`, provider-specific code under `providers/`, and focused tests under `packages/rag-core/tests/unit/test_adapters/`.

#### LangGraph Pipelines (`packages/graphs/src/rag_graphs/`)

Define new graphs in `packages/graphs/src/rag_graphs/`. Depend on `rag-core` for shared utilities; do not duplicate parsing, embedding, or vector-store logic.

#### Layering Boundaries (`rag-core`, `apps/backend`, `packages/graphs`)

To prevent blurred responsibilities, duplication, and configuration leakage:
- **Stateful/Database Connections (Backend Only)**: The LangGraph runner (`packages/graphs`) must **never** connect directly to databases (PostgreSQL, Qdrant, Redis, etc.) or use their client drivers. All retrieval, document state checks, and metadata queries must be routed through `apps/backend` API endpoints (e.g. using `search_multi_knowledge_bases`).
- **Stateless LLM & Computation Utilities (Shared/Dual Run)**: Stateless operations (e.g., `QueryRewriter`, `TreeSummarizer`, `SynonymExpander`, `CitationValidator`) belong to `rag-core` and can be imported and executed directly in both `packages/graphs` (within the Aegra server) and `apps/backend`. They must remain stateless, requiring no direct database handles or persistent local storage.

### Backend (`apps/backend`)

- Keep API routes under feature packages in `apps/backend/app/features/**/api/`.
- Keep business flows in `usecases/`, persistence in `repos.py`, transport schemas in `schemas.py`, and database models in `models.py`.
- Worker entry points live under `apps/backend/app/worker/`; use `just worker` or `just dev backend` to run them.
- When backend API schemas change, run `just gen-ui-api` and include the generated web client changes.

#### CPU-Bound & Heavy Tasks Decoupling (Strict Guideline)

Heavy CPU/GPU work must run outside the FastAPI/FastStream processes. Workers orchestrate only; parser engines belong under [infra/services](infra/services/docker-compose.yml), model runtimes belong under [infra/models](infra/models/docker-compose.yml), and backend code calls them over network APIs. Never import or run large model/parser frameworks directly in the main API or worker process. Lightweight token estimation utilities such as `tiktoken` are allowed in-process.


### Frontend (`apps/web`)

- **Tech Stack**: React 19, TypeScript, Vite, CopilotKit, TanStack Query, Ant Design, generated OpenAPI client.
- **Node**: `>=24.0.0` / **npm**: `>=11.0.0` (see `.nvmrc` and `apps/web/package.json`).
- **Markdown rendering**: Use `react-markdown` + `rehype-sanitize` + `remark-gfm`. Never render raw user or LLM HTML without sanitization.
- **API calls**: Use the generated API client in `apps/web/src/generated/api/`. Do not add raw `fetch` calls to backend endpoints unless no client path exists yet.
- **Build**: Use `just check web` or `npm --prefix apps/web run build`.

---

## Testing

Use `just test` for default Python tests and `just test-file <path>` for focused pytest paths. Pytest roots and async settings live in `pyproject.toml`; add focused tests for new adapters, chunkers, graph nodes, backend use cases, and API behavior.

---

## Critical Constraints

1. Never commit secrets, PII, `.env`, or `models.yaml`; do not paste local config into docs, logs, commits, fixtures, or final responses.
2. Never execute `git commit` automatically. If asked for a commit message, use concise imperative text with no emoji.
3. Before finalizing code changes, run the relevant `just` verification scope or explain why it was not run.
4. After backend API/schema changes, run `just gen-ui-api` and include generated client updates.
