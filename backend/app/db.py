"""Database engine, table creation and session handling."""

from collections.abc import Iterator
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def build_engine(database_url: str) -> Engine:
    """Create the engine. Kept separate so tests can build an in-memory one."""
    connect_args: dict[str, object] = {}
    extra_options: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        # SQLite refuses connections shared across threads by default,
        # but FastAPI runs sync routes in a thread pool.
        connect_args["check_same_thread"] = False
    if database_url == "sqlite://":
        # In-memory: every new connection would be a new, empty database.
        # StaticPool reuses a single connection, so all threads see the same data.
        extra_options["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, **extra_options)


# One engine per process: it owns the connection pool.
engine: Engine = build_engine(get_settings().database_url)


# Columns added to tables that already existed. create_all() only creates
# missing TABLES, never missing columns, so each new column on an old table
# needs an entry here: (table, column, SQL type and default).
# If this list grows, it's time to switch to Alembic (proper migrations, like
# EF Core's Add-Migration).
ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("job", "tags", "JSON NOT NULL DEFAULT '[]'"),
    ("profile", "preferred_stack", "JSON NOT NULL DEFAULT '[]'"),
    ("profile", "strict_unknown_work_mode", "BOOLEAN NOT NULL DEFAULT 0"),
]


def add_missing_columns(db_engine: Engine) -> None:
    """Minimal migration: ALTER TABLE ... ADD COLUMN for columns listed above."""
    inspector = inspect(db_engine)
    with db_engine.begin() as connection:  # begin(): one transaction, committed at the end
        for table, column, definition in ADDED_COLUMNS:
            existing = {info["name"] for info in inspector.get_columns(table)}
            if column not in existing:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def init_db(db_engine: Engine = engine) -> None:
    """Create missing tables and columns (no-op when everything exists)."""
    # Importing the module is what registers the table classes in the metadata.
    # It's kept next to create_all to make that hidden dependency explicit.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(db_engine)
    add_missing_columns(db_engine)


def get_session() -> Iterator[Session]:
    """Yield a session and close it afterwards. Used as a FastAPI dependency."""
    # "with" guarantees the session is closed even if an exception happens.
    with Session(engine) as session:
        yield session
