"""
Custom assertion helpers for app_tests.
"""

from typing import Any

from app_layer_base.core.log import logger
from httpx import Response


def assert_status_code(response: Response, expected: int):
    """Assert HTTP response status code with detailed error message."""
    if 400 <= expected < 600:
        # For error responses, log that this is expected for this test case
        logger.info(f"[Expected Error] Status {expected} is expected for this test case")
    assert response.status_code == expected, (
        f"Expected status {expected}, got {response.status_code}. Response: {response.text[:500]}"
    )


def assert_json_contains(response: Response, expected: dict):
    """Assert that response JSON contains expected key-value pairs."""
    data = response.json()
    for key, value in expected.items():
        assert key in data, f"Key '{key}' not found in response"
        assert data[key] == value, f"Expected {key}={value}, got {data[key]}"


def assert_paginated_response(response: Response, min_items: int = 0):
    """Assert that response is a valid paginated response."""
    assert_status_code(response, 200)
    data = response.json()
    assert "items" in data, "Response missing 'items' field"
    assert "total_count" in data, "Response missing 'total_count' field"
    assert isinstance(data["items"], list), "'items' should be a list"
    assert len(data["items"]) >= min_items, f"Expected at least {min_items} items"


def assert_error_response(response: Response, status_code: int, error_type: str | None = None):
    """Assert that response is an error response."""
    assert_status_code(response, status_code)
    data = response.json()
    assert "detail" in data or "error" in data, "Error response missing detail/error field"
    if error_type:
        assert data.get("error_type") == error_type


def assert_model_fields(obj: Any, expected: dict):
    """Assert that model object has expected field values."""
    for key, value in expected.items():
        actual = getattr(obj, key, None)
        assert actual == value, f"Expected {key}={value}, got {actual}"
