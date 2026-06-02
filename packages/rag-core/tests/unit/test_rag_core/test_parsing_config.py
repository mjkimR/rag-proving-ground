from rag_core.parsers import (
    KnowledgeParsingConfig,
    knowledge_parsing_config_hash,
    knowledge_parsing_config_payload,
    resolve_knowledge_parsing_config,
)


def test_resolve_knowledge_parsing_config_uses_provider_override() -> None:
    config = resolve_knowledge_parsing_config({"provider": "docling"}, provider_override="marker")

    assert config.provider == "marker"


def test_knowledge_parsing_config_hash_changes_with_provider() -> None:
    docling = KnowledgeParsingConfig(provider="docling")
    marker = KnowledgeParsingConfig(provider="marker")

    assert knowledge_parsing_config_hash(docling) != knowledge_parsing_config_hash(marker)


def test_knowledge_parsing_config_payload_keeps_extra_options() -> None:
    config = resolve_knowledge_parsing_config({"provider": "docling", "ocr": True})

    assert knowledge_parsing_config_payload(config) == {"provider": "docling", "ocr": True}
