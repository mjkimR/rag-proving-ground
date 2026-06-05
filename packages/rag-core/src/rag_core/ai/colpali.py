"""Infinity API 연동용 ColPali 클라이언트."""

from __future__ import annotations

import asyncio
import base64
import io

import httpx
from app_http_client import get_http_client
from loguru import logger
from PIL import Image

from rag_core.config import get_colpali_settings


class ColPaliModel:
    # 원격 Infinity 서버 부하 과부하 및 커넥션 고갈을 예방하기 위한 동시성 제어 세마포어
    _semaphore = asyncio.Semaphore(4)

    def __init__(self, model_name: str = "vidore/colpali-v1.2-merged"):
        self.model_name = model_name
        self.settings = get_colpali_settings()

    async def _post_embeddings(self, payload: dict) -> dict:
        url = f"{self.settings.base_url}/embeddings"
        client = get_http_client()
        async with self._semaphore:
            try:
                response = await client.post(url, json=payload, timeout=self.settings.timeout)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error(f"Failed to communicate with Infinity serving engine: {exc}")
                raise RuntimeError("Embedding generation failed due to remote server error.") from exc
        return response.json()

    async def encode_queries(self, queries: list[str]) -> list[list[list[float]]]:
        """텍스트 쿼리를 Infinity에 요청하여 멀티 벡터 임베딩을 가져옵니다."""
        payload = {"model": self.model_name, "input": queries}
        data = await self._post_embeddings(payload)
        return [item["embedding"] for item in data["data"]]

    async def encode_images(self, images: list[Image.Image]) -> list[list[list[float]]]:
        """PIL 이미지를 Base64 인코딩하여 Infinity에 요청하고 멀티 벡터 임베딩을 가져옵니다."""
        formatted_inputs = []
        for img in images:
            buffered = io.BytesIO()
            # 용량 최소화 및 전송 속도 향상을 위해 JPEG 포맷(quality=80)으로 인코딩
            img.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            formatted_inputs.append({"image": f"data:image/jpeg;base64,{img_str}"})

        payload = {
            "model": self.model_name,
            "input": formatted_inputs,
            "encoding_format": "base64",  # 이미지 전송 시 필수
        }
        data = await self._post_embeddings(payload)
        return [item["embedding"] for item in data["data"]]

    @property
    def embedding_dim(self) -> int:
        # colpali-v1.2 및 colSmol의 임베딩 차원은 기본 128입니다.
        return 128
