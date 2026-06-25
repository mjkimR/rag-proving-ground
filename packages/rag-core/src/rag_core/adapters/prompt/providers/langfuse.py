import json
from pathlib import Path
from typing import Any

from langfuse import Langfuse
from loguru import logger

from rag_core.adapters.prompt.interface import PromptProvider
from rag_core.config import get_prompt_settings


class LangfusePromptProvider(PromptProvider):
    name = "langfuse"

    def __init__(self, fallback_dir: str, public_key: str | None, secret_key: str | None, host: str):
        self.fallback_dir = Path(fallback_dir)
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

    def get_prompt(self, name: str, version: str | int | None = None) -> Any:
        if self.client:
            try:
                # langfuse client get_prompt syntax: get_prompt(name, version)
                # where version can be an integer. It returns a PromptClient object.
                # If we need the actual template text or compiled module, we can extract it.
                langfuse_prompt = self.client.get_prompt(name, version=int(version) if version else None)
                # By default, we might just return the raw prompt object or extract the prompt string.
                # Here we just return the object, which can be formatted via `langfuse_prompt.compile()`
                return langfuse_prompt
            except Exception as e:
                logger.error(f"Failed to fetch prompt '{name}' from Langfuse: {e}")

        logger.warning(f"Trying fallback for prompt {name}")
        return self._get_fallback_prompt(name)

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

        raise FileNotFoundError(f"Prompt '{name}' not found in Langfuse or local fallback directory.")
