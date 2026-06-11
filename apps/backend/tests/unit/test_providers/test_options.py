from app.features.providers.usecases.options import GetProviderOptionsUseCase


async def test_get_provider_options_use_case(mocker) -> None:
    mock_get = mocker.patch("app.features.providers.usecases.options.get_model_options")
    mock_get.return_value = {
        "embedding_models": ["mock-embed", "vllm-embedding"],
        "llm_models": ["mock-llm"],
        "reranker_models": ["mock-rerank"],
    }

    use_case = GetProviderOptionsUseCase()
    options = await use_case.execute()

    assert options.embedding_models == ["mock-embed", "vllm-embedding"]
    assert options.llm_models == ["mock-llm"]
    assert options.reranker_models == ["mock-rerank"]
    assert "docling" in options.parser_providers
