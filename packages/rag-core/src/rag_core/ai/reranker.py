"""LangChain document compressor backed by LiteLLM rerank."""

from collections.abc import Sequence
from typing import Any, cast

import litellm
import tiktoken
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from loguru import logger
from pydantic import ConfigDict, Field, SecretStr


def _truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    if not text:
        return text
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoding.decode(tokens[:max_tokens])
    except Exception as e:
        logger.warning(f"Failed to encode tokens via tiktoken, falling back to character slicing: {e}")
        return text[: int(max_tokens * 1.5)]


class LiteLLMRerankCompressor(BaseDocumentCompressor):
    """Rerank LangChain documents through a LiteLLM gateway."""

    model: str
    api_base: str
    api_key: SecretStr
    top_n: int | None = None
    score_metadata_key: str = "relevance_score"
    request_timeout: float | None = None
    max_retries: int | None = None
    max_tokens_per_doc: int = 400
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

        truncated_docs = [_truncate_text_to_tokens(doc.page_content, self.max_tokens_per_doc) for doc in documents]

        rerank = cast(Any, litellm.rerank)
        response = rerank(
            model=self.model,
            query=query,
            documents=truncated_docs,
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

        truncated_docs = [_truncate_text_to_tokens(doc.page_content, self.max_tokens_per_doc) for doc in documents]

        arerank = cast(Any, litellm.arerank)
        response = await arerank(
            model=self.model,
            query=query,
            documents=truncated_docs,
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
