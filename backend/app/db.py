"""Database engine, table creation and session handling."""

from collections.abc import Iterator
from typing import Any

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


def init_db(db_engine: Engine = engine) -> None:
    """Create all tables registered in SQLModel.metadata (no-op if they exist)."""
    # Importing the module is what registers the table classes in the metadata.
    # It's kept next to create_all to make that hidden dependency explicit.
    import app.models  # noqa: F401

    SQLModel.metadata.create_all(db_engine)


def get_session() -> Iterator[Session]:
    """Yield a session and close it afterwards. Used as a FastAPI dependency."""
    # "with" guarantees the session is closed even if an exception happens.
    with Session(engine) as session:
        yield session
