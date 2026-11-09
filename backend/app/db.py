"""Database engine, table creation and session handling."""

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def build_engine(database_url: str) -> Engine:
    """Create the engine. Kept separate so tests can build an in-memory one."""
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        # SQLite refuses connections shared across threads by default,
        # but FastAPI runs sync routes in a thread pool.
        connect_args["check_same_thread"] = False
    return create_engine(database_url, connect_args=connect_args)


# One engine per process: it owns the connection pool.
engine: Engine = build_engine(get_settings().database_url)


def init_db() -> None:
    """Create all tables registered in SQLModel.metadata (no-op if they exist)."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """Yield a session and close it afterwards. Used as a FastAPI dependency."""
    # "with" guarantees the session is closed even if an exception happens.
    with Session(engine) as session:
        yield session
