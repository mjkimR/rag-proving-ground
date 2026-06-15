from types import SimpleNamespace

from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseConfigApplyMode, KnowledgeBasePatch
from app.features.knowledge.knowledge_bases.usecases.crud import (
    KnowledgeBaseConfigChangeSet,
    _detect_config_changes,
    _prepare_existing_documents_for_config_update,
)
from rag_core.chunkers import ChunkingConfig
from rag_core.embeddings import KnowledgeEmbeddingConfig
from rag_core.parsers import KnowledgeParsingConfig


def test_detect_config_changes_ignores_unset_patch_fields() -> None:
    kb = SimpleNamespace(
        default_parsing_config={"provider": "docling"},
        default_chunking_config={"chunk_size": 450, "chunk_overlap": 50},
        embedding_config={"model": "test-embedding", "distance": "cosine"},
    )
    patch = KnowledgeBasePatch(name="renamed")

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert not change_set.has_changes


def test_detect_config_changes_normalizes_pydantic_configs() -> None:
    kb = SimpleNamespace(
        default_parsing_config={"provider": "docling"},
        default_chunking_config=ChunkingConfig(chunk_size=450, chunk_overlap=50).model_dump(mode="json"),
        embedding_config={"model": "test-embedding", "distance": "cosine"},
    )
    patch = KnowledgeBasePatch(
        default_parsing_config=KnowledgeParsingConfig(provider="marker"),
        default_chunking_config=ChunkingConfig(chunk_size=450, chunk_overlap=50),
        embedding_config=KnowledgeEmbeddingConfig(model="test-embedding"),
    )

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert change_set.parsing_changed
    assert not change_set.chunking_changed
    assert not change_set.embedding_changed
    assert change_set.target_status == KnowledgeBaseDocumentStatus.PENDING_REPARSE


def test_inherited_only_marks_only_documents_inheriting_changed_config() -> None:
    inherited_doc = SimpleNamespace(
        parsing_config=None,
        chunking_config={"chunk_size": 128},
        status=KnowledgeBaseDocumentStatus.COMPLETED,
    )
    overridden_doc = SimpleNamespace(
        parsing_config={"provider": "docling"},
        chunking_config=None,
        status=KnowledgeBaseDocumentStatus.COMPLETED,
    )

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[inherited_doc, overridden_doc],
        kb=SimpleNamespace(default_parsing_config={"provider": "docling"}, default_chunking_config=None),
        change_set=KnowledgeBaseConfigChangeSet(parsing_changed=True),
        apply_mode=KnowledgeBaseConfigApplyMode.INHERITED_ONLY,
    )

    assert updated_docs == [inherited_doc]
    assert inherited_doc.status == KnowledgeBaseDocumentStatus.PENDING_REPARSE
    assert overridden_doc.status == KnowledgeBaseDocumentStatus.COMPLETED


def test_force_all_resets_document_overrides_and_marks_target_status() -> None:
    doc = SimpleNamespace(
        parsing_config={"provider": "marker"},
        chunking_config={"chunk_size": 128},
        status=KnowledgeBaseDocumentStatus.COMPLETED,
    )

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[doc],
        kb=SimpleNamespace(default_parsing_config=None, default_chunking_config=None),
        change_set=KnowledgeBaseConfigChangeSet(chunking_changed=True),
        apply_mode=KnowledgeBaseConfigApplyMode.FORCE_ALL,
    )

    assert updated_docs == [doc]
    assert doc.parsing_config is None
    assert doc.chunking_config is None
    assert doc.status == KnowledgeBaseDocumentStatus.PENDING_RECHUNK


def test_new_only_freezes_inherited_configs_without_marking_reprocess_status() -> None:
    inherited_doc = SimpleNamespace(
        parsing_config=None,
        chunking_config=None,
        status=KnowledgeBaseDocumentStatus.COMPLETED,
    )
    overridden_doc = SimpleNamespace(
        parsing_config={"provider": "marker"},
        chunking_config={"chunk_size": 128},
        status=KnowledgeBaseDocumentStatus.COMPLETED,
    )
    kb = SimpleNamespace(
        default_parsing_config={"provider": "docling"},
        default_chunking_config={"chunk_size": 450, "chunk_overlap": 50},
    )

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[inherited_doc, overridden_doc],
        kb=kb,
        change_set=KnowledgeBaseConfigChangeSet(parsing_changed=True, chunking_changed=True),
        apply_mode=KnowledgeBaseConfigApplyMode.NEW_ONLY,
    )

    assert updated_docs == [inherited_doc]
    assert inherited_doc.parsing_config == {"provider": "docling"}
    assert inherited_doc.chunking_config == {"chunk_size": 450, "chunk_overlap": 50}
    assert inherited_doc.status == KnowledgeBaseDocumentStatus.COMPLETED
    assert overridden_doc.parsing_config == {"provider": "marker"}
    assert overridden_doc.chunking_config == {"chunk_size": 128}


def test_detect_config_changes_compares_embedding_configs_after_defaults_resolve() -> None:
    kb = SimpleNamespace(
        default_parsing_config=None,
        default_chunking_config=None,
        embedding_config={"model": "vllm-embedding", "distance": "cosine"},
    )
    patch = KnowledgeBasePatch(embedding_config=None)

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert not change_set.embedding_changed


def test_detect_config_changes_ignores_identical_parsed_config_with_different_field_subsets() -> None:
    kb = SimpleNamespace(
        default_parsing_config={"provider": "docling"},
        default_chunking_config={"chunk_size": 450},
        embedding_config={"model": "vllm-embedding", "distance": "cosine"},
    )
    # The patch includes default_parsing_config and default_chunking_config with identical logical values
    # but as full Pydantic models. They should be evaluated as NOT changed.
    patch = KnowledgeBasePatch(
        default_parsing_config=KnowledgeParsingConfig(provider="docling"),
        default_chunking_config=ChunkingConfig(chunk_size=450),
    )

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert not change_set.parsing_changed
    assert not change_set.chunking_changed
    assert not change_set.embedding_changed

