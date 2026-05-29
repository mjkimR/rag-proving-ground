"""LangChain document compressor backed by LiteLLM rerank."""

from collections.abc import Sequence
from typing import Any

import litellm
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from pydantic import ConfigDict, Field, SecretStr


class LiteLLMRerankCompressor(BaseDocumentCompressor):
    """Rerank LangChain documents through a LiteLLM gateway."""

    model: str
    api_base: str
    api_key: SecretStr
    top_n: int | None = None
    score_metadata_key: str = "relevance_score"
    request_timeout: float | None = None
    max_retries: int | None = None
    rerank_kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []

        response = litellm.rerank(
            model=self.model,
            query=query,
            documents=[document.page_content for document in documents],
            custom_llm_provider="litellm_proxy",
            top_n=self.top_n,
            return_documents=False,
            api_base=self.api_base,
            api_key=self.api_key.get_secret_value(),
            timeout=self.request_timeout,
            num_retries=self.max_retries,
            **self.rerank_kwargs,
        )
        return self._documents_from_results(documents, response.get("results") or [])

    async def acompress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        if not documents:
            return []

        response = await litellm.arerank(
            model=self.model,
            query=query,
            documents=[document.page_content for document in documents],
            custom_llm_provider="litellm_proxy",
            top_n=self.top_n,
            return_documents=False,
            api_base=self.api_base,
            api_key=self.api_key.get_secret_value(),
            timeout=self.request_timeout,
            num_retries=self.max_retries,
            **self.rerank_kwargs,
        )
        return self._documents_from_results(documents, response.get("results") or [])

    def _documents_from_results(
        self,
        documents: Sequence[Document],
        results: Sequence[dict[str, Any]],
    ) -> list[Document]:
        reranked: list[Document] = []
        for result in results:
            index = result.get("index")
            if not isinstance(index, int) or index < 0 or index >= len(documents):
                continue

            document = documents[index]
            metadata = dict(document.metadata)
            metadata[self.score_metadata_key] = result.get("relevance_score")
            reranked.append(document.model_copy(update={"metadata": metadata}))
            if self.top_n is not None and len(reranked) >= self.top_n:
                break
        return reranked
