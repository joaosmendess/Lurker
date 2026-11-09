"""Shared fixtures. pytest loads conftest.py automatically for every test in this folder."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db import build_engine, get_session, init_db
from app.main import app
from app.models import Job
from app.routers.companies import get_http_client


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
def fake_web() -> dict[str, httpx.Response]:
    """What the API's HTTP client answers, by URL path. A test adds the pages it needs;
    any other request fails the test, so the API never reaches a real site in tests."""
    return {}


@pytest.fixture
def client(engine: Engine, fake_web: dict[str, httpx.Response]) -> Iterator[TestClient]:
    """API client wired to the test database (uses whichever "engine" fixture is active)."""

    def override_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    def answer(request: httpx.Request) -> httpx.Response:
        response = fake_web.get(request.url.path)
        if response is None:
            # AssertionError isn't an httpx error, so no "except" in the app swallows it
            raise AssertionError(f"Unexpected HTTP request in a test: {request.url}")
        return response

    def override_get_http_client() -> Iterator[httpx.Client]:
        # MockTransport: the client calls answer() instead of opening a connection
        with httpx.Client(transport=httpx.MockTransport(answer)) as http_client:
            yield http_client

    # Swap the real database for the test one, like replacing a service in
    # WebApplicationFactory.ConfigureTestServices
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_http_client] = override_get_http_client
    yield TestClient(app)  # not "with": skips lifespan, so the real DB is never touched
    app.dependency_overrides.clear()
