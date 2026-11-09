from sqlalchemy import text
from sqlmodel import Session

from app.db import build_engine


def test_in_memory_engine_runs_queries() -> None:
    engine = build_engine("sqlite://")  # "sqlite://" with no path = in-memory database

    with Session(engine) as session:
        result = session.connection().execute(text("SELECT 1")).scalar()

    assert result == 1
