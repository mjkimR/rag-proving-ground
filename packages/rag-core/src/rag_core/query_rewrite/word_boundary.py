import re
from abc import ABC, abstractmethod
from functools import lru_cache

from loguru import logger


class WordBoundaryStrategy(ABC):
    """Abstract base class representing a word boundary matching strategy for synonym expansion."""

    @abstractmethod
    def get_pattern(self, keyword: str) -> re.Pattern[str]:
        """Generate a compiled regex pattern for matching the keyword at correct word boundaries."""
        pass


@lru_cache(maxsize=4096)
def _compile_korean_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![a-zA-Z0-9가-힣]){re.escape(keyword)}(?![a-zA-Z0-9])",
        re.IGNORECASE,
    )


@lru_cache(maxsize=4096)
def _compile_english_pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(
        rf"\b{re.escape(keyword)}\b",
        re.IGNORECASE,
    )


class KoreanWordBoundaryStrategy(WordBoundaryStrategy):
    """Word boundary strategy for Korean queries.

    Allows Korean postpositions (조사) to follow the keyword at the end, but prevents
    partial matches inside other English/Korean words at the start.
    """

    def get_pattern(self, keyword: str) -> re.Pattern[str]:
        return _compile_korean_pattern(keyword)


class EnglishWordBoundaryStrategy(WordBoundaryStrategy):
    """Word boundary strategy for English queries.

    Uses strict word boundaries (\b) to prevent partial substring matches.
    """

    def get_pattern(self, keyword: str) -> re.Pattern[str]:
        return _compile_english_pattern(keyword)


def get_word_boundary_strategy(language: str | None) -> WordBoundaryStrategy:
    """Factory to retrieve a WordBoundaryStrategy for the specified language."""
    lang_lower = language.lower() if language else "en"
    if lang_lower == "ko":
        return KoreanWordBoundaryStrategy()
    return EnglishWordBoundaryStrategy()


def clear_word_boundary_cache() -> None:
    """Clears the LRU caches of compiled word boundary patterns."""
    _compile_korean_pattern.cache_clear()
    _compile_english_pattern.cache_clear()
    logger.debug("Word boundary compiled pattern caches cleared.")
