from functools import lru_cache

from .base import BaseTokenizer
from .fallback import EnglishFallbackTokenizer, KoreanFallbackTokenizer
from .tiktoken import TiktokenTokenizer
from .wrapper import FallbackWrapperTokenizer


@lru_cache(maxsize=4)
def _get_primary_tokenizer(model_name_or_encoding: str | None = None) -> BaseTokenizer:
    return TiktokenTokenizer(model_name_or_encoding)


@lru_cache(maxsize=2)
def _get_fallback_tokenizer(language: str) -> BaseTokenizer:
    lang_lower = language.lower() if language else "en"
    return KoreanFallbackTokenizer() if lang_lower == "ko" else EnglishFallbackTokenizer()


def get_tokenizer(
    language: str = "en",
    model_name_or_encoding: str | None = None,
) -> BaseTokenizer:
    """Factory to get the tokenizer strategy with language-specific fallback.

    Args:
        language: Language code, e.g. "en" or "ko". Defaults to "en".
        model_name_or_encoding: Optional model name (e.g. "gpt-4o") or encoding name.

    Returns:
        BaseTokenizer: The resolved tokenizer strategy wrapper.
    """
    primary = _get_primary_tokenizer(model_name_or_encoding)
    fallback = _get_fallback_tokenizer(language)
    return FallbackWrapperTokenizer(primary=primary, fallback=fallback)
