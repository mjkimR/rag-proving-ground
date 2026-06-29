from abc import ABC, abstractmethod
from typing import Any, ClassVar


class PromptProvider(ABC):
    """Base interface for prompt registry providers (e.g., S3, Langfuse)."""

    name: ClassVar[str]

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
