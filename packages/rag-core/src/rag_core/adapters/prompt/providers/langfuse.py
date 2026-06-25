import asyncio
from typing import Any

from langfuse import Langfuse
from loguru import logger

from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.config import get_prompt_settings


class LangfusePromptProvider(PromptProvider):
    name = "langfuse"

    def __init__(self, fallback_dir: str, public_key: str | None, secret_key: str | None, host: str):
        super().__init__(fallback_dir)
        # Only initialize if keys are provided to avoid immediate crash if unused
        self.client = None
        if public_key and secret_key:
            self.client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
        else:
            logger.warning("Langfuse credentials missing. Will rely entirely on fallback.")

    @classmethod
    def from_config(cls) -> "LangfusePromptProvider":
        settings = get_prompt_settings()
        return cls(
            fallback_dir=settings.fallback_dir,
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    def _fetch_from_langfuse(self, name: str, version: str | int | None = None) -> Any:
        if not self.client:
            raise RuntimeError("Langfuse client is not initialized.")

        if version is not None:
            if isinstance(version, int) or (isinstance(version, str) and version.isdigit()):
                return self.client.get_prompt(name, version=int(version))
            else:
                return self.client.get_prompt(name, label=str(version))
        else:
            return self.client.get_prompt(name)

    async def get_prompt(self, name: str, version: str | int | None = None) -> Any:
        if self.client:
            try:
                # Run the blocking Langfuse client call in a worker thread
                langfuse_prompt = await asyncio.to_thread(self._fetch_from_langfuse, name, version)
                return langfuse_prompt
            except Exception as e:
                logger.error(f"Failed to fetch prompt '{name}' from Langfuse: {e}")

        logger.warning(f"Trying fallback for prompt {name}")
        return self._get_fallback_prompt(name)
