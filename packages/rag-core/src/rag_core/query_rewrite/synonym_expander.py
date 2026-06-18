import re
from collections.abc import Awaitable, Callable

from loguru import logger

# Global cached synonyms mapping: keyword -> list of synonyms
_CACHED_SYNONYMS: dict[str, list[str]] = {}
_IS_LOADED = False

# Async loader callback registry
_SYNONYM_LOADER_FN: Callable[[], Awaitable[dict[str, list[str]]]] | None = None


def register_synonym_loader(loader_fn: Callable[[], Awaitable[dict[str, list[str]]]]) -> None:
    """Registers the dynamic database/repository loader function for synonyms."""
    global _SYNONYM_LOADER_FN
    _SYNONYM_LOADER_FN = loader_fn
    logger.info("Synonym loader callback registered successfully in rag-core.")


def clear_synonyms_cache() -> None:
    """Invalidates the in-memory cache, forcing a reload on the next query."""
    global _IS_LOADED, _CACHED_SYNONYMS
    _IS_LOADED = False
    _CACHED_SYNONYMS.clear()
    logger.info("Synonyms in-memory cache cleared in rag-core.")


async def get_synonyms() -> dict[str, list[str]]:
    """Retrieves the synonyms map, triggering the registered loader if cache is empty."""
    global _IS_LOADED, _CACHED_SYNONYMS
    if not _IS_LOADED and _SYNONYM_LOADER_FN is not None:
        try:
            _CACHED_SYNONYMS = await _SYNONYM_LOADER_FN()
            _IS_LOADED = True
            logger.debug(f"Loaded {len(_CACHED_SYNONYMS)} synonym mappings into memory.")
        except Exception as e:
            logger.error(f"Failed to load synonyms using registered loader: {e}")
    return _CACHED_SYNONYMS


class SynonymExpander:
    """Applies dictionary-based synonym expansions to search queries."""

    async def expand_query(self, query: str) -> str:
        """Appends synonyms in parentheses for matching keywords.

        Uses regex to match keywords as whole words (to prevent partial matches).
        """
        synonyms_dict = await get_synonyms()
        if not synonyms_dict:
            return query

        expanded_query = query
        for keyword, synonyms in synonyms_dict.items():
            if not keyword or not synonyms:
                continue

            # Case-insensitive matching, checking word boundary.
            # Prevent partial matches inside other English/Korean words at the start,
            # but allow Korean postpositions at the end (only block alphanumeric suffixes).
            pattern = re.compile(
                rf"(?<![a-zA-Z0-9가-힣]){re.escape(keyword)}(?![a-zA-Z0-9])",
                re.IGNORECASE,
            )
            if pattern.search(query):
                synonym_str = ", ".join(synonyms)
                replacement = f"{keyword} ({synonym_str})"
                expanded_query = pattern.sub(replacement, expanded_query)
                logger.debug(f"Expanded keyword '{keyword}' -> '{replacement}' in query.")

        return expanded_query
