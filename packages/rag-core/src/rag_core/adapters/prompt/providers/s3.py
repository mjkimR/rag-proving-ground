from typing import Any

import yaml
from app_file_storage import get_storage_client
from loguru import logger

from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.config import get_prompt_settings


class S3PromptProvider(PromptProvider):
    name = "s3"

    def __init__(self, bucket: str, fallback_dir: str):
        super().__init__(fallback_dir)
        self.bucket = bucket
        self.storage = get_storage_client()

    @classmethod
    def from_config(cls) -> "S3PromptProvider":
        settings = get_prompt_settings()
        return cls(bucket=settings.s3_bucket, fallback_dir=settings.fallback_dir)

    async def get_prompt(self, name: str, version: str | int | None = None) -> Any:
        for ext in ["yaml", "txt"]:
            object_key = f"{name}.{ext}"
            try:
                content_bytes = await self.storage.download_file(self.bucket, object_key)
                if content_bytes is not None:
                    content_str = content_bytes.decode("utf-8")
                    if ext == "yaml":
                        return yaml.safe_load(content_str)
                    return content_str
            except Exception as e:
                logger.debug(f"Failed to fetch {object_key} from S3: {e}")

        logger.warning(f"Prompt {name} not found in S3 bucket {self.bucket}, trying fallback")
        return self._get_fallback_prompt(name)
