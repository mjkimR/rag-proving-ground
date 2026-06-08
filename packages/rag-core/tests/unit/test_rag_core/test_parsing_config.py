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
    payload = knowledge_parsing_config_payload(config)

    assert payload.get("provider") == "docling"
    assert payload.get("ocr") is True
    assert payload.get("native_max_page_chars") == 2000


def test_resolve_knowledge_parsing_config_with_extension_overrides() -> None:
    config = resolve_knowledge_parsing_config(
        {"provider": "docling", "extension_providers": {"txt": "native_text", ".md": "markdown_parser"}}
    )

    # Normalized keys in dict (e.g. txt -> .txt)
    assert config.extension_providers == {".txt": "native_text", ".md": "markdown_parser"}
    assert config.get_provider_for_filename("test.txt") == "native_text"
    assert config.get_provider_for_filename("TEST.MD") == "markdown_parser"
    assert config.get_provider_for_filename("document.pdf") == "docling"
