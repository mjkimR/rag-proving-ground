import re

from loguru import logger

from .base import BaseTokenizer


class BaseFallbackTokenizer(BaseTokenizer):
    """Base fallback tokenizer containing shared input validation, encode/decode logic, and unicode error handling."""

    def _validate_text(self, text: str) -> str:
        if text is None:
            return ""
        return text

    def _validate_tokens(self, tokens: list[int]) -> list[int]:
        if tokens is None:
            return []
        return tokens

    def encode(self, text: str) -> list[int]:
        validated_text = self._validate_text(text)
        return [ord(c) for c in validated_text]

    def decode(self, tokens: list[int]) -> str:
        validated_tokens = self._validate_tokens(tokens)
        decoded_chars = []
        for t in validated_tokens:
            try:
                decoded_chars.append(chr(t))
            except Exception as e:
                # Log a detailed warning and use Unicode replacement character to prevent silent data loss
                logger.warning(f"Failed to decode fallback token ID '{t}' to character: {e}")
                decoded_chars.append("\ufffd")
        return "".join(decoded_chars)


class EnglishFallbackTokenizer(BaseFallbackTokenizer):
    """Fallback tokenizer for English."""

    def count_tokens(self, text: str) -> int:
        validated_text = self._validate_text(text)
        if not validated_text:
            return 0
        return max(1, int(len(validated_text) * 0.25))

    def truncate(self, text: str, max_tokens: int) -> str:
        validated_text = self._validate_text(text)
        return validated_text[: int(max_tokens * 4.0)]


class KoreanFallbackTokenizer(BaseFallbackTokenizer):
    """Fallback tokenizer for Korean."""

    _HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")

    def count_tokens(self, text: str) -> int:
        validated_text = self._validate_text(text)
        if not validated_text:
            return 0
        hangul_chars = len(self._HANGUL_PATTERN.findall(validated_text))
        other_chars = len(validated_text) - hangul_chars
        return int(hangul_chars * 1.5 + other_chars * 0.25)

    def truncate(self, text: str, max_tokens: int) -> str:
        validated_text = self._validate_text(text)
        # Slicing limit: since minimum cost per character is 0.25,
        # we can never include more than max_tokens * 4 characters.
        limit = int(max_tokens * 4)
        truncated_text = validated_text[:limit]

        current_tokens = 0.0
        idx = 0
        for char in truncated_text:
            char_cost = 1.5 if "\uac00" <= char <= "\ud7a3" else 0.25
            if current_tokens + char_cost > max_tokens:
                break
            current_tokens += char_cost
            idx += 1
        return truncated_text[:idx]
