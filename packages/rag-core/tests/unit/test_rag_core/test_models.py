import pytest
from rag_core.ai import gateway, models
from rag_core.ai.models import (
    get_embedding_model,
    get_llm_model,
    get_model_metadata,
    get_reranker_model,
)


def test_get_model_metadata_returns_correct_params(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_model_list = [
        {
            "model_name": "test-llm",
            "metadata": {
                "role": "llm",
                "model_params": {
                    "temperature": 0.5,
                    "max_tokens": 100,
                    "top_p": 0.9,
                },
            },
        },
        {
            "model_name": "test-embed",
            "metadata": {
                "role": "embedding",
                "model_params": {
                    "chunk_size": 256,
                    "max_retries": 5,
                },
            },
        },
    ]
    # Clear cache before test
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    metadata = get_model_metadata("test-llm")
    assert metadata.get("role") == "llm"
    assert metadata.get("model_params") == {
        "temperature": 0.5,
        "max_tokens": 100,
        "top_p": 0.9,
    }


def test_get_llm_model_merges_model_params(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_model_list = [
        {
            "model_name": "test-llm",
            "metadata": {
                "role": "llm",
                "model_params": {
                    "temperature": 0.5,
                    "max_tokens": 100,
                    "top_p": 0.9,
                },
            },
        }
    ]
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    # We mock ChatLiteLLM to intercept what is passed
    chat_init_args = {}

    class FakeChatLiteLLM:
        def __init__(self, **kwargs):
            nonlocal chat_init_args
            chat_init_args = kwargs

        def bind(self, **kwargs):
            return self

    monkeypatch.setattr(models, "ChatLiteLLM", FakeChatLiteLLM)

    # Clean model cache so a new instance is created
    models._LLM_MODEL_CACHE.clear()

    get_llm_model(model_name="test-llm")

    assert chat_init_args.get("temperature") == 0.5
    assert chat_init_args.get("max_tokens") == 100
    assert chat_init_args.get("top_p") == 0.9


def test_get_embedding_model_merges_model_params(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_model_list = [
        {
            "model_name": "test-embed",
            "metadata": {
                "role": "embedding",
                "model_params": {
                    "chunk_size": 256,
                    "max_retries": 5,
                },
            },
        }
    ]
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    embed_init_args = {}

    class FakeLiteLLMEmbeddings:
        def __init__(self, **kwargs):
            nonlocal embed_init_args
            embed_init_args = kwargs

    monkeypatch.setattr(models, "LiteLLMEmbeddings", FakeLiteLLMEmbeddings)
    models._EMBEDDING_MODEL_CACHE.clear()

    get_embedding_model(model_name="test-embed")

    assert embed_init_args.get("chunk_size") == 256
    assert embed_init_args.get("max_retries") == 5


def test_get_reranker_model_merges_model_params(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_model_list = [
        {
            "model_name": "test-reranker",
            "metadata": {
                "role": "reranker",
                "model_params": {
                    "top_n": 3,
                    "max_retries": 4,
                },
            },
        }
    ]
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    rerank_init_args = {}

    class FakeLiteLLMRerankCompressor:
        def __init__(self, **kwargs):
            nonlocal rerank_init_args
            rerank_init_args = kwargs

    monkeypatch.setattr(models, "LiteLLMRerankCompressor", FakeLiteLLMRerankCompressor)
    models._RERANKER_MODEL_CACHE.clear()

    get_reranker_model(model_name="test-reranker")

    assert rerank_init_args.get("top_n") == 3
    assert rerank_init_args.get("max_retries") == 4


def test_temperature_is_not_forced_if_none(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_model_list = [
        {
            "model_name": "test-llm-no-temp",
            "metadata": {
                "role": "llm",
                "model_params": {
                    "max_tokens": 100,
                },
            },
        }
    ]
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    # Mock settings to have temperature = None
    settings = models.get_litellm_settings()
    monkeypatch.setattr(settings, "temperature", None)

    chat_init_args = {}

    class FakeChatLiteLLM:
        def __init__(self, **kwargs):
            nonlocal chat_init_args
            chat_init_args = kwargs

    monkeypatch.setattr(models, "ChatLiteLLM", FakeChatLiteLLM)
    models._LLM_MODEL_CACHE.clear()

    get_llm_model(model_name="test-llm-no-temp")

    assert "temperature" not in chat_init_args


def test_resolve_model_params_fallback_explicit_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # If a yaml param is explicitly None, it should fall back to settings.
    mock_model_list = [
        {
            "model_name": "test-llm-explicit-none",
            "metadata": {
                "role": "llm",
                "model_params": {
                    "temperature": None,
                    "max_tokens": 150,
                },
            },
        }
    ]
    gateway.fetch_raw_model_info_from_gateway.cache_clear()
    gateway._get_model_metadata_map.cache_clear()
    monkeypatch.setattr(gateway, "fetch_raw_model_info_from_gateway", lambda: mock_model_list)

    # Set mock settings
    settings = models.get_litellm_settings()
    monkeypatch.setattr(settings, "temperature", 0.8)

    chat_init_args = {}

    class FakeChatLiteLLM:
        def __init__(self, **kwargs):
            nonlocal chat_init_args
            chat_init_args = kwargs

        def bind(self, **kwargs):
            return self

    monkeypatch.setattr(models, "ChatLiteLLM", FakeChatLiteLLM)
    models._LLM_MODEL_CACHE.clear()

    get_llm_model(model_name="test-llm-explicit-none")

    # temperature is None in yaml_model_params, so it should fall back to settings.temperature (0.8)
    assert chat_init_args.get("temperature") == 0.8
    assert chat_init_args.get("max_tokens") == 150
