import asyncio
from logging.config import fileConfig

from alembic import context
from app_layer_base.base.models.mixin import Base
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
import sqlalchemy as sa

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

target_metadata = Base.metadata
from app.main import create_app  # noqa: F401, E402

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url() -> str:
    from app_layer_base.config import get_app_settings

    return get_app_settings().DATABASE_URL


def compare_type(context, inspected_column, metadata_column, inspected_type, metadata_type):
    """Custom type comparison function for Alembic.
    
    It overrides the default type comparison behavior for specific database dialects.
    Currently configured to ignore UUID type for SQLite database.
    """
    
    # Ignore UUID type for SQLite
    if context.dialect.name == "sqlite":
        if isinstance(metadata_type, sa.UUID):
            return False
    return None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
    )

    with context.begin_transaction():
        context.run_migrations()


# Using Asyncio with Alembic
# https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
def do_run_migrations(connection):
    def process_revision_directives(context, revision, directives):
        if config.cmd_opts is None:
            print("No command options detected.")
            return
        if config.cmd_opts.autogenerate:
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                print("No changes in schema detected.")

    def render_item(type_, obj, autogen_context):
        """Add imports for JSONB astext_type."""
        if type_ == "type" and hasattr(obj, "dialect_impl"):
            # Check if this is a JSONB variant
            from sqlalchemy.dialects import postgresql
            dialect_impl = obj.dialect_impl(postgresql.dialect())
            if isinstance(dialect_impl, postgresql.JSONB):
                # Ensure Text is imported
                autogen_context.imports.add("from sqlalchemy import Text")
        return False

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        compare_type=compare_type,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    configuration = config.get_section(config.config_ini_section)
    if configuration is None:
        raise RuntimeError("No configuration found.")

    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
