from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.collect import CollectResult
from app.models import CollectRun, utc_now
from app.routers import collect as collect_router


@pytest.fixture
def fake_runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replaces the real collection (it would hit the network) and records each call."""
    calls: list[str] = []

    def fake_run_collection() -> CollectResult:
        calls.append("run")
        return CollectResult(fetched=1, saved=1)

    monkeypatch.setattr(collect_router, "run_collection", fake_run_collection)
    return calls


@pytest.fixture(autouse=True)
def release_lock() -> Iterator[None]:
    """Make sure a failing test never leaves the module-level lock held for the next one."""
    yield
    if collect_router._collect_lock.locked():
        collect_router._collect_lock.release()


def add_run(engine: Engine, minutes_ago: int, **fields: object) -> None:
    with Session(engine) as session:
        session.add(CollectRun(started_at=utc_now() - timedelta(minutes=minutes_ago), **fields))
        session.commit()


def test_status_without_runs(client: TestClient) -> None:
    assert client.get("/collect").json() == {
        "running": False,
        "cooldown_until": None,
        "last_run": None,
    }


def test_post_starts_a_background_collection(client: TestClient, fake_runs: list[str]) -> None:
    response = client.post("/collect")

    assert response.status_code == 202
    # TestClient runs background tasks before returning, so it already ran
    assert fake_runs == ["run"]
    assert collect_router._collect_lock.locked() is False  # released at the end


def test_post_during_cooldown_is_429(
    client: TestClient, engine: Engine, fake_runs: list[str]
) -> None:
    add_run(engine, minutes_ago=10)

    response = client.post("/collect")

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert fake_runs == []


def test_post_after_cooldown_is_accepted(
    client: TestClient, engine: Engine, fake_runs: list[str]
) -> None:
    add_run(engine, minutes_ago=121)  # default cooldown is 120 minutes

    assert client.post("/collect").status_code == 202
    assert fake_runs == ["run"]


def test_post_while_running_is_409(client: TestClient, fake_runs: list[str]) -> None:
    collect_router._collect_lock.acquire()  # simulate a collection in progress

    response = client.post("/collect")

    assert response.status_code == 409
    assert fake_runs == []


def test_status_shows_last_run_and_cooldown(client: TestClient, engine: Engine) -> None:
    add_run(engine, minutes_ago=200, fetched=5)
    add_run(engine, minutes_ago=30, fetched=10, saved=3, failed_sources=["gupy"])

    body = client.get("/collect").json()

    assert body["running"] is False
    assert body["cooldown_until"] is not None
    assert body["last_run"]["fetched"] == 10  # the newest one
    assert body["last_run"]["failed_sources"] == ["gupy"]


def test_failed_background_collection_still_releases_the_lock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_run_collection() -> CollectResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(collect_router, "run_collection", broken_run_collection)

    assert client.post("/collect").status_code == 202
    assert collect_router._collect_lock.locked() is False
