"""Alembic environment.

The database URL and target metadata are pulled from the application itself
so migrations can never drift from the runtime configuration or the models.
An explicit `-x db_url=...` overrides the configured URL, which lets ops and
the migration test target a specific database.
"""

from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401  (populate Base.metadata)

config = context.config

_override = context.get_x_argument(as_dictionary=True).get("db_url")
_database_url = _override or settings.DATABASE_URL
config.set_main_option("sqlalchemy.url", _database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=_database_url.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    engine = create_engine(_database_url, future=True)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # SQLite cannot ALTER in place; batch mode rebuilds the table.
            render_as_batch=_database_url.startswith("sqlite"),
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()