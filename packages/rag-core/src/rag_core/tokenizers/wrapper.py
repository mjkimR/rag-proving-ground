from loguru import logger

from .base import BaseTokenizer


class FallbackWrapperTokenizer(BaseTokenizer):
    """Tokenizer strategy wrapping a primary tokenizer and a fallback tokenizer."""

    def __init__(self, primary: BaseTokenizer, fallback: BaseTokenizer) -> None:
        self.primary = primary
        self.fallback = fallback
        self._count_tokens_broken = False
        self._encode_broken = False
        self._decode_broken = False
        self._truncate_broken = False

    def count_tokens(self, text: str) -> int:
        if not self._count_tokens_broken:
            try:
                return self.primary.count_tokens(text)
            except Exception as e:
                logger.warning(
                    f"Primary tokenizer count_tokens failed: {e}. Switching count_tokens to fallback mode permanently."
                )
                self._count_tokens_broken = True
        return self.fallback.count_tokens(text)

    def encode(self, text: str) -> list[int]:
        if not self._encode_broken:
            try:
                return self.primary.encode(text)
            except Exception as e:
                logger.warning(f"Primary tokenizer encode failed: {e}. Switching encode to fallback mode permanently.")
                self._encode_broken = True
        return self.fallback.encode(text)

    def decode(self, tokens: list[int]) -> str:
        if not self._decode_broken:
            try:
                return self.primary.decode(tokens)
            except Exception as e:
                logger.warning(f"Primary tokenizer decode failed: {e}. Switching decode to fallback mode permanently.")
                self._decode_broken = True
        return self.fallback.decode(tokens)

    def truncate(self, text: str, max_tokens: int) -> str:
        if not self._truncate_broken:
            try:
                return self.primary.truncate(text, max_tokens)
            except Exception as e:
                logger.warning(
                    f"Primary tokenizer truncate failed: {e}. Switching truncate to fallback mode permanently."
                )
                self._truncate_broken = True
        return self.fallback.truncate(text, max_tokens)
