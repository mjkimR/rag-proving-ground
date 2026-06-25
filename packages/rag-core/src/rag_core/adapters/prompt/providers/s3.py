import json
from pathlib import Path
from typing import Any

from app_file_storage import get_storage_client
from loguru import logger

from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.config import get_prompt_settings


class S3PromptProvider(PromptProvider):
    name = "s3"

    def __init__(self, bucket: str, fallback_dir: str):
        self.bucket = bucket
        self.fallback_dir = Path(fallback_dir)
        self.storage = get_storage_client()

    @classmethod
    def from_config(cls) -> "S3PromptProvider":
        settings = get_prompt_settings()
        return cls(bucket=settings.s3_bucket, fallback_dir=settings.fallback_dir)

    async def get_prompt_async(self, name: str, version: str | int | None = None) -> Any:
        for ext in ["yaml", "txt"]:
            object_key = f"{name}.{ext}"
            try:
                content_bytes = await self.storage.download_file(self.bucket, object_key)
                if content_bytes is not None:
                    content_str = content_bytes.decode("utf-8")
                    if ext == "yaml":
                        import yaml
                        return yaml.safe_load(content_str)
                    return content_str
            except Exception as e:
                logger.debug(f"Failed to fetch {object_key} from S3: {e}")

        logger.warning(f"Prompt {name} not found in S3 bucket {self.bucket}, trying fallback")
        return self._get_fallback_prompt(name)

    def get_prompt(self, name: str, version: str | int | None = None) -> Any:
        """
        Since download_file is async but get_prompt is a sync interface per design,
        we execute the async storage method synchronously.
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.get_prompt_async(name, version))
        else:
            return asyncio.run(self.get_prompt_async(name, version))

    def _get_fallback_prompt(self, name: str) -> Any:
        for ext in ["yaml", "txt"]:
            fallback_path = self.fallback_dir / f"{name}.{ext}"
            if fallback_path.exists():
                logger.info(f"Loaded fallback prompt from {fallback_path}")
                content = fallback_path.read_text(encoding="utf-8")
                if ext == "yaml":
                    import yaml
                    return yaml.safe_load(content)
                return content

        raise FileNotFoundError(f"Prompt '{name}' not found in S3 or local fallback directory.")
