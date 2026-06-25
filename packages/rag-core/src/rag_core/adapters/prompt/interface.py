from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

import yaml
from loguru import logger


class PromptProvider(ABC):
    """Base interface for prompt registry providers (e.g., S3, Langfuse)."""

    name: ClassVar[str]

    def __init__(self, fallback_dir: str | Path):
        self.fallback_dir = Path(fallback_dir)

    @classmethod
    @abstractmethod
    def from_config(cls) -> "PromptProvider":
        """Creates a prompt provider instance from application settings/configuration.

        Returns:
            PromptProvider: An instance of the prompt provider.
        """
        pass

    @abstractmethod
    async def get_prompt(self, name: str, version: str | int | None = None) -> Any:
        """Retrieves a prompt from the provider by name and optional version.

        Args:
            name: The name/ID of the prompt to retrieve.
            version: The version of the prompt. If None, retrieves the latest active version.

        Returns:
            Any: The prompt payload. Could be a string, dict, Langfuse prompt object, or dspy.Module.
        """
        pass

    def _get_fallback_prompt(self, name: str) -> Any:
        for ext in ["yaml", "txt"]:
            fallback_path = self.fallback_dir / f"{name}.{ext}"
            if fallback_path.exists():
                logger.info(f"Loaded fallback prompt from {fallback_path}")
                content = fallback_path.read_text(encoding="utf-8")
                if ext == "yaml":
                    return yaml.safe_load(content)
                return content

        raise FileNotFoundError(f"Prompt '{name}' not found in {self.name} or local fallback directory.")
