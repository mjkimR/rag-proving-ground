"""ColPali 멀티 벡터 전용 Qdrant VectorStore."""

from __future__ import annotations

import asyncio
import contextlib
import io
import uuid
from typing import Any

from app_file_storage import get_storage_client
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from loguru import logger
from PIL import Image
from qdrant_client.http import models as qmodels

from rag_core.ai.colpali import ColPaliModel


class ColPaliQdrantStore(VectorStore):
    def __init__(
        self,
        client: Any,
        async_client: Any,
        collection_name: str,
        colpali_model: ColPaliModel,
        storage_client: Any = None,
    ):
        self.client = client
        self.async_client = async_client
        self.collection_name = collection_name
        self.colpali_model = colpali_model
        self._storage_client = storage_client

    @property
    def storage_client(self) -> Any:
        if self._storage_client is None:
            self._storage_client = get_storage_client()
        return self._storage_client

    async def _download_image(self, img_path: str | None) -> Image.Image | None:
        if not img_path:
            return None
        try:
            img_bytes = await self.storage_client.download_file(img_path)
            return Image.open(io.BytesIO(img_bytes))
        except Exception as exc:
            logger.warning(f"Failed to download page image from storage (path: {img_path}): {exc}")
            return None

    async def aadd_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        points = []
        point_ids = []

        # OOM 및 네트워크 타임아웃 방지를 위한 4개 단위 미니 배치 루프
        batch_size = 4
        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i : i + batch_size]

            # asyncio.gather를 통한 이미지 파일 병렬 다운로드 진행
            tasks = [self._download_image(doc.metadata.get("image_storage_path")) for doc in batch_docs]
            downloaded_images = await asyncio.gather(*tasks)

            images = []
            valid_docs = []
            for doc, img in zip(batch_docs, downloaded_images, strict=False):
                if img is not None:
                    images.append(img)
                    valid_docs.append(doc)

            if not images:
                continue

            try:
                # Infinity를 통한 고속 원격 임베딩
                embeddings = await self.colpali_model.encode_images(images)
            finally:
                for img in images:
                    with contextlib.suppress(Exception):
                        img.close()

            for doc, embedding in zip(valid_docs, embeddings, strict=False):
                pt_id = str(uuid.uuid4())
                points.append(
                    qmodels.PointStruct(
                        id=pt_id,
                        vector=embedding,  # list[list[float]] (멀티 벡터)
                        payload={"page_content": doc.page_content, "metadata": doc.metadata},
                    )
                )
                point_ids.append(pt_id)

        if points:
            await self.async_client.upsert(collection_name=self.collection_name, points=points)
        return point_ids

    async def asimilarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        *,
        filter: Any | None = None,
        **kwargs: Any,
    ) -> list[tuple[Document, float]]:
        # 1. Infinity 클라이언트를 사용해 쿼리 임베딩 획득
        query_embeddings = await self.colpali_model.encode_queries([query])
        query_vector = query_embeddings[0]

        # 2. Qdrant 멀티벡터 MAX_SIM 쿼리 실행
        results = await self.async_client.query_points(
            collection_name=self.collection_name, query=query_vector, query_filter=filter, limit=k, with_payload=True
        )

        output = []
        for point in results.points:
            doc = Document(
                page_content=point.payload.get("page_content", ""), metadata=point.payload.get("metadata", {})
            )
            output.append((doc, point.score))
        return output

    def similarity_search(self, query: str, k: int = 4, **kwargs: Any) -> list[Document]:
        raise NotImplementedError("Use asimilarity_search_with_score instead.")

    @classmethod
    def from_texts(
        cls, texts: list[str], embedding: Any, metadatas: list[dict] | None = None, **kwargs: Any
    ) -> ColPaliQdrantStore:
        raise NotImplementedError("Requires image-based documents.")
