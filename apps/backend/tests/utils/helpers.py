"""
Common test helper functions.
"""

import uuid


def random_email() -> str:
    """Generate a random email for testing."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def random_string(prefix: str = "test") -> str:
    """Generate a random string for testing."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def create_and_get(client, endpoint: str, data: dict) -> dict:
    """Create a resource via API and return the response data."""
    response = await client.post(endpoint, json=data)
    assert response.status_code == 201, f"Create failed: {response.text}"
    return response.json()


async def cleanup_resource(client, endpoint: str, resource_id: str):
    """Delete a resource via API."""
    await client.delete(f"{endpoint}/{resource_id}")


async def clean_db_after_test(driver_name: str, tables, conn):
    """Utility function to clean the database after app_tests."""
    from sqlalchemy import text

    # Only delete from tables that actually exist in the database.
    # Mock models defined in unit test conftest files are registered in
    # Base.metadata but may not have been created in the DB.
    if "sqlite" in driver_name:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    else:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
    existing_table_names = {row[0] for row in result}
    existing_tables = [t for t in tables if t.name in existing_table_names]

    if "sqlite" in driver_name:
        await conn.execute(text("PRAGMA foreign_keys = OFF;"))
        for table in existing_tables:
            await conn.execute(text(f"DELETE FROM {table.name}"))
        await conn.execute(text("PRAGMA foreign_keys = ON;"))
        await conn.commit()
    else:  # driver_name == "postgresql":
        table_names = [table.name for table in existing_tables]
        if table_names:
            query = f"TRUNCATE {', '.join(table_names)} RESTART IDENTITY CASCADE;"
            await conn.execute(text(query))
            await conn.commit()
