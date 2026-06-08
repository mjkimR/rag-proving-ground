from types import SimpleNamespace

from app.features.knowledge.knowledge_base_documents.schemas import KnowledgeBaseDocumentStatus
from app.features.knowledge.knowledge_bases.schemas import KnowledgeBaseConfigApplyMode, KnowledgeBasePatch
from app.features.knowledge.knowledge_bases.usecases.crud import (
    _detect_config_changes,
    _prepare_existing_documents_for_config_update,
)
from rag_core.chunkers import ChunkingConfig
from rag_core.parsers import KnowledgeParsingConfig


def test_detect_config_changes_for_patch_only_checks_provided_fields() -> None:
    kb = SimpleNamespace(
        default_parsing_config={"provider": "docling"},
        default_chunking_config={"chunk_size": 450},
        embedding_config={"model": "embedding-a", "distance": "cosine"},
    )
    patch = KnowledgeBasePatch(default_chunking_config=ChunkingConfig(chunk_size=800))

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert not change_set.parsing_changed
    assert change_set.chunking_changed
    assert not change_set.embedding_changed
    assert change_set.target_status == KnowledgeBaseDocumentStatus.PENDING_RECHUNK


def test_detect_config_changes_compares_embedding_configs_after_defaults_resolve() -> None:
    kb = SimpleNamespace(
        default_parsing_config=None,
        default_chunking_config=None,
        embedding_config={"model": "vllm-embedding", "distance": "cosine"},
    )
    patch = KnowledgeBasePatch(embedding_config=None)

    change_set = _detect_config_changes(kb, patch, partial=True)

    assert not change_set.embedding_changed


def test_inherited_only_marks_only_documents_inheriting_changed_config() -> None:
    kb = SimpleNamespace(default_parsing_config={"provider": "docling"}, default_chunking_config={"chunk_size": 450})
    change_set = _detect_config_changes(
        kb, KnowledgeBasePatch(default_parsing_config=KnowledgeParsingConfig(provider="marker")), partial=True
    )
    inherited_doc = SimpleNamespace(parsing_config=None, chunking_config={"chunk_size": 100}, status="COMPLETED")
    custom_doc = SimpleNamespace(parsing_config={"provider": "docling"}, chunking_config=None, status="COMPLETED")

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[inherited_doc, custom_doc],
        kb=kb,
        change_set=change_set,
        apply_mode=KnowledgeBaseConfigApplyMode.INHERITED_ONLY,
    )

    assert inherited_doc.status == KnowledgeBaseDocumentStatus.PENDING_REPARSE
    assert custom_doc.status == "COMPLETED"
    assert updated_docs == [inherited_doc]


def test_new_only_freezes_inherited_configs_without_status_transition() -> None:
    kb = SimpleNamespace(default_parsing_config={"provider": "docling"}, default_chunking_config={"chunk_size": 450})
    change_set = _detect_config_changes(
        kb,
        KnowledgeBasePatch(
            default_parsing_config=KnowledgeParsingConfig(provider="marker"),
            default_chunking_config=ChunkingConfig(chunk_size=800),
        ),
        partial=True,
    )
    doc = SimpleNamespace(parsing_config=None, chunking_config=None, status="COMPLETED")

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[doc],
        kb=kb,
        change_set=change_set,
        apply_mode=KnowledgeBaseConfigApplyMode.NEW_ONLY,
    )

    assert doc.parsing_config == {"provider": "docling"}
    assert doc.chunking_config == {"chunk_size": 450}
    assert doc.status == "COMPLETED"
    assert updated_docs == [doc]


def test_force_all_resets_custom_configs_and_uses_highest_cost_status() -> None:
    kb = SimpleNamespace(default_parsing_config={"provider": "docling"}, default_chunking_config={"chunk_size": 450})
    change_set = _detect_config_changes(
        kb,
        KnowledgeBasePatch(
            default_parsing_config=KnowledgeParsingConfig(provider="marker"),
            default_chunking_config=ChunkingConfig(chunk_size=800),
        ),
        partial=True,
    )
    doc = SimpleNamespace(
        parsing_config={"provider": "custom"},
        chunking_config={"chunk_size": 100},
        status="COMPLETED",
    )

    updated_docs = _prepare_existing_documents_for_config_update(
        docs=[doc],
        kb=kb,
        change_set=change_set,
        apply_mode=KnowledgeBaseConfigApplyMode.FORCE_ALL,
    )

    assert doc.parsing_config is None
    assert doc.chunking_config is None
    assert doc.status == KnowledgeBaseDocumentStatus.PENDING_REPARSE
    assert updated_docs == [doc]


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
