from datetime import datetime

from sqlalchemy import inspect
from sqlmodel import Session

from app.db import build_engine, init_db
from app.models import Job


def make_job(job_id: str = "remotive:1") -> Job:
    return Job(
        id=job_id,
        source="remotive",
        title="Backend Developer",
        company="Acme",
        url="https://example.com/jobs/1",
    )


def test_init_db_creates_job_table() -> None:
    engine = build_engine("sqlite://")

    init_db(engine)

    assert "job" in inspect(engine).get_table_names()


def test_job_round_trip() -> None:
    engine = build_engine("sqlite://")
    init_db(engine)

    with Session(engine) as session:
        session.add(make_job())
        session.commit()

    # New session: proves the data came from the database, not from memory
    with Session(engine) as session:
        saved = session.get(Job, "remotive:1")

    assert saved is not None
    assert saved.title == "Backend Developer"
    assert saved.remote is None  # unknown by default
    assert isinstance(saved.collected_at, datetime)


def test_each_job_gets_its_own_collected_at() -> None:
    first = make_job("remotive:1")
    second = make_job("remotive:2")

    # default_factory runs per instance, so the timestamps differ
    assert first.collected_at <= second.collected_at
    assert first.collected_at is not second.collected_at
