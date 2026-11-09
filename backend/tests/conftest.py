"""Shared fixtures. pytest loads conftest.py automatically for every test in this folder."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db import build_engine, get_session, init_db
from app.main import app
from app.models import Job


def make_job(job_id: str, title: str = "Desenvolvedor Pleno", **fields: object) -> Job:
    values: dict[str, object] = {
        "id": job_id,
        "source": job_id.split(":")[0],
        "title": title,
        "company": "Acme",
        "url": f"https://example.com/{job_id}",
        "remote": True,
        "description": "word " * 100,  # long enough to be cut in the preview
    }
    values.update(fields)
    return Job.model_validate(values)


@pytest.fixture(autouse=True)
def no_configured_network_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sources built from settings (GitHub repos) would hit the network in any test
    that builds the real source list. Tests never call real sites, so they're off."""
    monkeypatch.setattr("app.collect.github_sources", lambda: {})


@pytest.fixture
def engine() -> Engine:
    """Empty in-memory database. A test module can override it with seeded data."""
    test_engine = build_engine("sqlite://")
    init_db(test_engine)
    return test_engine


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """API client wired to the test database (uses whichever "engine" fixture is active)."""

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    # Swap the real database for the test one, like replacing a service in
    # WebApplicationFactory.ConfigureTestServices
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)  # not "with": skips lifespan, so the real DB is never touched
    app.dependency_overrides.clear()
