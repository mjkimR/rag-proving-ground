from app.features.knowledge.knowledge_base_documents.facade.pipeline import (
    knowledge_original_file_key,
    knowledge_parsed_data_key,
    resolve_chunking_config,
)


def test_resolve_chunking_config_applies_defaults_to_partial_config() -> None:
    config = resolve_chunking_config({"chunk_size": 800})

    assert config.chunk_size == 800
    assert config.chunk_overlap == 50


def test_knowledge_storage_keys_resolved_under_file_hash() -> None:
    assert knowledge_original_file_key("kb", "abc123", "doc.pdf") == "knowledge/kb/abc123/doc.pdf"
    assert knowledge_parsed_data_key("kb", "abc123") == "knowledge/kb/abc123/parsed_data.json"
