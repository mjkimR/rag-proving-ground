from abc import ABC, abstractmethod


class BaseTokenizer(ABC):
    """Abstract base class representing a tokenizer strategy."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Counts the tokens in the given text."""
        pass

    @abstractmethod
    def encode(self, text: str) -> list[int]:
        """Encodes the text into token IDs."""
        pass

    @abstractmethod
    def decode(self, tokens: list[int]) -> str:
        """Decodes token IDs back into text."""
        pass

    @abstractmethod
    def truncate(self, text: str, max_tokens: int) -> str:
        """Truncates text to fit within the max_tokens limit."""
        pass
