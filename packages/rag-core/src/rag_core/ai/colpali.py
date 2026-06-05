"""ColPali client for Infinity API integration."""

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
    # Concurrency control semaphore to prevent remote Infinity server overload and connection exhaustion
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
        """Requests multi-vector embeddings for text queries from Infinity."""
        payload = {"model": self.model_name, "input": queries}
        data = await self._post_embeddings(payload)
        return [item["embedding"] for item in data["data"]]

    async def encode_images(self, images: list[Image.Image]) -> list[list[list[float]]]:
        """Base64-encodes PIL images, requests multi-vector embeddings from Infinity, and retrieves them."""
        formatted_inputs = []
        for img in images:
            buffered = io.BytesIO()
            # Encode to JPEG format (quality=80) to minimize size and improve transmission speed
            img.save(buffered, format="JPEG", quality=80)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            formatted_inputs.append({"image": f"data:image/jpeg;base64,{img_str}"})

        payload = {
            "model": self.model_name,
            "input": formatted_inputs,
            "encoding_format": "base64",  # Required for image transmission
        }
        data = await self._post_embeddings(payload)
        return [item["embedding"] for item in data["data"]]

    @property
    def embedding_dim(self) -> int:
        # The default embedding dimension for colpali-v1.2 and colSmol is 128.
        return 128
