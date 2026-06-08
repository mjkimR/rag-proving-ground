from rag_core.chunkers.schemas import (
    ChunkingConfig,
    knowledge_chunking_config_hash,
    resolve_chunking_config,
)


def test_resolve_chunking_config_handles_none_and_dict() -> None:
    # None returns default ChunkingConfig
    default_config = resolve_chunking_config(None)
    assert isinstance(default_config, ChunkingConfig)
    assert default_config.chunk_size == 450
    assert default_config.chunk_overlap == 50

    # Dict returns instantiated ChunkingConfig with overrides
    custom_config = resolve_chunking_config({"chunk_size": 1000, "chunk_overlap": 100})
    assert isinstance(custom_config, ChunkingConfig)
    assert custom_config.chunk_size == 1000
    assert custom_config.chunk_overlap == 100


def test_resolve_chunking_config_returns_same_instance() -> None:
    config = ChunkingConfig(chunk_size=500)
    resolved = resolve_chunking_config(config)
    assert resolved is config


def test_knowledge_chunking_config_hash_is_stable() -> None:
    config1 = ChunkingConfig(chunk_size=500, chunk_overlap=50)
    config2 = ChunkingConfig(chunk_size=500, chunk_overlap=50)

    hash1 = knowledge_chunking_config_hash(config1)
    hash2 = knowledge_chunking_config_hash(config2)

    assert isinstance(hash1, str)
    assert len(hash1) == 16
    assert hash1 == hash2


def test_knowledge_chunking_config_hash_changes_with_field_updates() -> None:
    config_base = ChunkingConfig(chunk_size=500)
    config_diff_size = ChunkingConfig(chunk_size=600)
    config_diff_overlap = ChunkingConfig(chunk_size=500, chunk_overlap=100)

    hash_base = knowledge_chunking_config_hash(config_base)
    hash_size = knowledge_chunking_config_hash(config_diff_size)
    hash_overlap = knowledge_chunking_config_hash(config_diff_overlap)

    assert hash_base != hash_size
    assert hash_base != hash_overlap
