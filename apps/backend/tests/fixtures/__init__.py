"""
Centralized fixtures package.
Import all fixtures from this package for easy access.
"""

from tests.fixtures.clients import (
    AsyncClientWithJson,
    app_fixture,
    client_fixture,
)
from tests.fixtures.db import (
    async_engine,
    db_url,
    session_fixture,
    setup_database,
)

__all__ = [
    # Client fixtures
    "AsyncClientWithJson",
    "app_fixture",
    "async_engine",
    "client_fixture",
    # Database fixtures
    "db_url",
    "session_fixture",
    "setup_database",
    # Auth fixtures (add auth fixtures here when available)
]
