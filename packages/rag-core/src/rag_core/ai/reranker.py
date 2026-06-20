"""LangChain document compressor backed by LiteLLM rerank."""

from collections.abc import Sequence
from typing import Any, cast

import litellm
from langchain_core.callbacks import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from pydantic import ConfigDict, Field, SecretStr

from rag_core.tokenizers import BaseTokenizer, get_tokenizer


class LiteLLMRerankCompressor(BaseDocumentCompressor):
    """LangChain document compressor utilizing the LiteLLM gateway's rerank API.

    Attributes:
        model: The name of the reranking model.
        api_base: The base URL of the LiteLLM gateway.
        api_key: The API key for authorization.
        top_n: The number of documents to return after reranking.
        score_metadata_key: The metadata key to store the relevance score under.
        request_timeout: The HTTP request timeout in seconds.
        max_retries: The maximum number of retries for the API request.
        max_tokens_per_doc: Maximum token length of document text to submit for reranking.
        rerank_kwargs: Additional parameters to pass to the LiteLLM rerank API.
    """

    model: str
    api_base: str
    api_key: SecretStr
    top_n: int | None = None
    score_metadata_key: str = "relevance_score"
    request_timeout: float | None = None
    max_retries: int | None = None
    max_tokens_per_doc: int = 400
    language: str = "en"
    rerank_kwargs: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_tokenizer(self) -> BaseTokenizer:
        return get_tokenizer(language=self.language, model_name_or_encoding=self.model)

    def _truncate_doc_text(self, text: str, tokenizer: BaseTokenizer | None = None) -> str:
        if not text:
            return text
        tok = tokenizer or self.get_tokenizer()
        return tok.truncate(text, self.max_tokens_per_doc)

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks | None = None,
    ) -> Sequence[Document]:
        """Compresses (reranks) the input documents for a given query synchronously.

        Args:
            documents: A sequence of LangChain Document objects to compress.
            query: The query text to relevance-score the documents against.
            callbacks: Optional callbacks to handle events.

        Returns:
            Sequence[Document]: The reranked documents with their relevance scores.
        """
        if not documents:
            return []

        tokenizer = self.get_tokenizer()
        truncated_docs = [self._truncate_doc_text(doc.page_content, tokenizer) for doc in documents]

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
        """Compresses (reranks) the input documents for a given query asynchronously.

        Args:
            documents: A sequence of LangChain Document objects to compress.
            query: The query text to relevance-score the documents against.
            callbacks: Optional callbacks to handle events.

        Returns:
            Sequence[Document]: The reranked documents with their relevance scores.
        """
        if not documents:
            return []

        tokenizer = self.get_tokenizer()
        truncated_docs = [self._truncate_doc_text(doc.page_content, tokenizer) for doc in documents]

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
