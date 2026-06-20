from loguru import logger

from .base import BaseTokenizer


class TiktokenTokenizer(BaseTokenizer):
    """Primary tokenizer strategy using tiktoken."""

    def __init__(self, model_name_or_encoding: str | None = None) -> None:
        self.model_name_or_encoding = model_name_or_encoding
        self.encoding = None
        self._init_tiktoken()

    def _init_tiktoken(self) -> None:
        name = self.model_name_or_encoding or "cl100k_base"
        try:
            import tiktoken

            try:
                self.encoding = tiktoken.encoding_for_model(name)
            except Exception:
                try:
                    self.encoding = tiktoken.get_encoding(name)
                except Exception as e:
                    logger.warning(
                        f"Failed to load tiktoken encoding for model/encoding '{name}': {e}. Trying cl100k_base."
                    )
                    self.encoding = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(
                f"Failed to initialize TiktokenTokenizer with model/encoding '{name}' or fallback cl100k_base: {e}. "
                "TiktokenTokenizer will remain uninitialized."
            )
            self.encoding = None

    def count_tokens(self, text: str) -> int:
        if self.encoding is None:
            raise RuntimeError("TiktokenTokenizer is not initialized.")
        return len(self.encoding.encode(text))

    def encode(self, text: str) -> list[int]:
        if self.encoding is None:
            raise RuntimeError("TiktokenTokenizer is not initialized.")
        return self.encoding.encode(text)

    def decode(self, tokens: list[int]) -> str:
        if self.encoding is None:
            raise RuntimeError("TiktokenTokenizer is not initialized.")
        return self.encoding.decode(tokens)

    def truncate(self, text: str, max_tokens: int) -> str:
        if self.encoding is None:
            raise RuntimeError("TiktokenTokenizer is not initialized.")
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens])
