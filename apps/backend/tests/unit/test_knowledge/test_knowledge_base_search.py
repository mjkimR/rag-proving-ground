from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from app.features.knowledge.knowledge_base_pages.repos import KnowledgeBasePageRepository
from app.features.knowledge.knowledge_bases.schemas import MultiKnowledgeBaseSearchRequest
from app.features.knowledge.knowledge_bases.services import KnowledgeBaseService
from app.features.knowledge.knowledge_bases.usecases import search
from app.features.knowledge.knowledge_bases.usecases.search import SearchMultiKnowledgeBaseUseCase
from fastapi import HTTPException
from rag_core.retrieval import RerankerConfig, RetrievedChunk


def test_multi_search_request_dedupes_ids_and_requires_reranker_for_unique_multi_kb() -> None:
    kb_id = uuid4()
    request = MultiKnowledgeBaseSearchRequest(
        queries=["test query"],
        knowledge_base_ids=[kb_id, kb_id],
    )

    assert request.knowledge_base_ids == [kb_id]

    with pytest.raises(ValueError, match="reranker_config is required"):
        MultiKnowledgeBaseSearchRequest(
            queries=["test query"],
            knowledge_base_ids=[uuid4(), uuid4()],
        )


def test_multi_search_request_rejects_reranker_top_n_below_limit() -> None:
    with pytest.raises(ValueError, match=r"reranker_config\.top_n"):
        MultiKnowledgeBaseSearchRequest(
            queries=["test query"],
            knowledge_base_ids=[uuid4(), uuid4()],
            limit=5,
            reranker_config=RerankerConfig(model="test-reranker", top_n=2),
        )


async def test_search_multi_knowledge_base_usecase_rejects_missing_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    existing_id = uuid4()
    missing_id = uuid4()
    use_case = SearchMultiKnowledgeBaseUseCase(
        cast(KnowledgeBaseService, _FakeService([_FakeKnowledgeBase(existing_id)])),
        cast(KnowledgeBasePageRepository, _FakeKnowledgeBasePageRepository()),
    )
    monkeypatch.setattr(search, "AsyncTransaction", _FakeTransaction)

    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(
            MultiKnowledgeBaseSearchRequest(
                queries=["test query"],
                knowledge_base_ids=[existing_id, missing_id],
                reranker_config=RerankerConfig(model="test-reranker"),
            )
        )

    assert exc_info.value.status_code == 404
    detail = cast(dict[str, Any], exc_info.value.detail)
    assert detail["missing_knowledge_base_ids"] == [str(missing_id)]


async def test_search_multi_knowledge_base_usecase_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    kb_id_1 = uuid4()
    kb_id_2 = uuid4()
    use_case = SearchMultiKnowledgeBaseUseCase(
        cast(
            KnowledgeBaseService,
            _FakeService(
                [
                    _FakeKnowledgeBase(kb_id_1),
                    _FakeKnowledgeBase(kb_id_2),
                ]
            ),
        ),
        cast(KnowledgeBasePageRepository, _FakeKnowledgeBasePageRepository()),
    )
    monkeypatch.setattr(search, "AsyncTransaction", _FakeTransaction)

    async def fake_retrieve_multi_knowledge_chunks(**kwargs):
        assert kwargs["query"] in ("test query", ["test query"])
        assert [kb_id for kb_id, _ in kwargs["kb_configs"]] == [kb_id_1, kb_id_2]
        assert kwargs["limit"] == 2
        assert kwargs["candidate_limit"] == 10
        assert kwargs["reranker_config"] == RerankerConfig(model="test-reranker", top_n=2)
        return [
            RetrievedChunk(
                chunk_id="chunk_1",
                doc_id="doc_1",
                content="content",
                score=0.8,
                knowledge_base_id=kb_id_2,
                vector_score=0.5,
                rerank_score=0.8,
            )
        ]

    monkeypatch.setattr(search, "retrieve_multi_knowledge_chunks", fake_retrieve_multi_knowledge_chunks)

    response = await use_case.execute(
        MultiKnowledgeBaseSearchRequest(
            queries=["test query"],
            knowledge_base_ids=[kb_id_1, kb_id_2],
            limit=2,
            candidate_limit=10,
            reranker_config=RerankerConfig(model="test-reranker", top_n=2),
        )
    )

    assert response.total == 1
    assert response.results[0].knowledge_base_id == kb_id_2
    assert response.results[0].score == 0.8
    assert response.results[0].vector_score == 0.5
    assert response.results[0].rerank_score == 0.8


async def test_search_multi_knowledge_base_usecase_dedupes_ids_when_called_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kb_id = uuid4()
    use_case = SearchMultiKnowledgeBaseUseCase(
        cast(KnowledgeBaseService, _FakeService([_FakeKnowledgeBase(kb_id)])),
        cast(KnowledgeBasePageRepository, _FakeKnowledgeBasePageRepository()),
    )
    monkeypatch.setattr(search, "AsyncTransaction", _FakeTransaction)

    async def fake_retrieve_multi_knowledge_chunks(**kwargs):
        assert [knowledge_base_id for knowledge_base_id, _ in kwargs["kb_configs"]] == [kb_id]
        return []

    monkeypatch.setattr(search, "retrieve_multi_knowledge_chunks", fake_retrieve_multi_knowledge_chunks)

    response = await use_case.execute(
        MultiKnowledgeBaseSearchRequest.model_construct(
            queries=["test query"],
            knowledge_base_ids=[kb_id, kb_id],
            limit=2,
            candidate_limit=None,
            reranker_config=None,
        )
    )

    assert response.total == 0


class _FakeTransaction:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _FakeColumn:
    def in_(self, values):
        return values


class _FakeRepo:
    model = SimpleNamespace(id=_FakeColumn())

    def __init__(self, knowledge_bases):
        self.knowledge_bases = knowledge_bases

    async def get_all(self, session, where):
        return self.knowledge_bases


class _FakeService:
    def __init__(self, knowledge_bases):
        self.repo = _FakeRepo(knowledge_bases)


class _FakeKnowledgeBase:
    def __init__(self, knowledge_base_id):
        self.id = knowledge_base_id
        self.name = "test_kb"
        self.language = "en"
        self.embedding_config = {"model": "test-embedding"}


class _FakeKnowledgeBasePageRepository:
    async def get_by_page_ids(self, session, page_ids):
        return []

    async def enrich_chunks_with_page_content(self, session, chunks):
        pass


async def test_search_use_case_fails_with_hybrid_override_on_dense_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseSearchRequest
    from app.features.knowledge.knowledge_bases.usecases.search import SearchKnowledgeBaseUseCase
    from rag_core.embeddings import RetrievalMode

    kb_id = uuid4()
    kb = _FakeKnowledgeBase(kb_id)
    # KB is dense because embedding_config defaults to {"model": "test-embedding"} which resolves to dense
    kb.embedding_config = {"model": "test-embedding", "retrieval_mode": "dense"}

    use_case = SearchKnowledgeBaseUseCase(
        cast(KnowledgeBaseService, _FakeService([kb])),
        cast(KnowledgeBasePageRepository, _FakeKnowledgeBasePageRepository()),
    )
    monkeypatch.setattr(search, "AsyncTransaction", _FakeTransaction)

    # We mock the repo.get_by_pk to return our mock KB
    async def fake_get_by_pk(session, pk_val):
        return kb

    use_case.service.repo.get_by_pk = fake_get_by_pk  # type: ignore[assignment]

    # Overriding dense KB search to hybrid should fail with HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        await use_case.execute(
            kb_id,
            KnowledgeBaseSearchRequest(
                queries=["test"],
                retrieval_mode=RetrievalMode.HYBRID,
            ),
        )
    assert exc_info.value.status_code == 400
    assert "cannot be searched in 'hybrid' mode" in exc_info.value.detail


async def test_search_use_case_succeeds_with_dense_override_on_hybrid_kb(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseSearchRequest
    from app.features.knowledge.knowledge_bases.usecases.search import SearchKnowledgeBaseUseCase
    from rag_core.embeddings import RetrievalMode

    kb_id = uuid4()
    kb = _FakeKnowledgeBase(kb_id)
    kb.embedding_config = {
        "model": "test-embedding",
        "retrieval_mode": "hybrid",
        "sparse_model": "en-bm25",
    }

    use_case = SearchKnowledgeBaseUseCase(
        cast(KnowledgeBaseService, _FakeService([kb])),
        cast(KnowledgeBasePageRepository, _FakeKnowledgeBasePageRepository()),
    )
    monkeypatch.setattr(search, "AsyncTransaction", _FakeTransaction)

    async def fake_get_by_pk(session, pk_val):
        return kb

    use_case.service.repo.get_by_pk = fake_get_by_pk  # type: ignore[assignment]

    resolved_configs_called = []

    async def fake_retrieve_knowledge_chunks(query, knowledge_base_id, embedding_config, limit):
        resolved_configs_called.append(embedding_config)
        return []

    monkeypatch.setattr(search, "retrieve_knowledge_chunks", fake_retrieve_knowledge_chunks)

    await use_case.execute(
        kb_id,
        KnowledgeBaseSearchRequest(
            queries=["test"],
            retrieval_mode=RetrievalMode.DENSE,
        ),
    )

    assert len(resolved_configs_called) == 1
    # Check that query-time override to dense is resolved correctly
    assert resolved_configs_called[0].retrieval_mode == RetrievalMode.DENSE
