"""Type conversion and safety casting utilities for parser providers."""

from typing import Any


def to_string(value: Any) -> str | None:
    """Safely convert a value to a string, returning None if not a string.

    Args:
        value: Any input value.

    Returns:
        The string if the input is a string, otherwise None.
    """
    if isinstance(value, str):
        return value
    return None


def to_dict(value: Any) -> dict[str, Any]:
    """Safely convert a value to a dict, returning empty dict if not a dict.

    Args:
        value: Any input value.

    Returns:
        The dictionary if the input is a dict, otherwise an empty dict.
    """
    if isinstance(value, dict):
        return value
    return {}


def to_dict_or_none(value: Any) -> dict[str, Any] | None:
    """Safely convert a value to a dict or None if not a dict.

    Args:
        value: Any input value.

    Returns:
        The dictionary if the input is a dict, otherwise None.
    """
    if isinstance(value, dict):
        return value
    return None


def to_list(value: Any) -> list[Any]:
    """Safely convert a value to a list, returning empty list if not a list.

    Args:
        value: Any input value.

    Returns:
        The list if the input is a list, otherwise an empty list.
    """
    if isinstance(value, list):
        return value
    return []


def to_int(value: Any) -> int | None:
    """Safely convert a value to an integer, returning None on failure.

    Args:
        value: Any input value.

    Returns:
        The integer value if conversion succeeds, otherwise None.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: Any) -> float | None:
    """Safely convert a value to a float, returning None on failure.

    Args:
        value: Any input value.

    Returns:
        The float value if conversion succeeds, otherwise None.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
