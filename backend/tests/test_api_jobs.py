from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db import build_engine, get_session, init_db
from app.main import app
from app.models import Job, Profile


def make_job(job_id: str, title: str, **fields: object) -> Job:
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


@pytest.fixture
def engine() -> Engine:
    test_engine = build_engine("sqlite://")
    init_db(test_engine)
    with Session(test_engine) as session:
        session.add_all(
            [
                make_job(
                    "gupy:1",
                    "Desenvolvedor .NET Pleno",
                    published_at=datetime(2026, 11, 3, tzinfo=UTC),
                ),
                make_job("gupy:2", "Estágio em TI", published_at=datetime(2026, 11, 2, tzinfo=UTC)),
                make_job(
                    "remotive:1",
                    "React Developer",
                    company="Globex",
                    published_at=datetime(2026, 11, 1, tzinfo=UTC),
                ),
                make_job("gupy:3", "Dev Presencial", remote=False, location="São Paulo"),
            ]
        )
        session.commit()
    return test_engine


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    def override_get_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    # Swap the real database for the test one, like replacing a service in
    # WebApplicationFactory.ConfigureTestServices
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)  # not "with": skips lifespan, so the real DB is never touched
    app.dependency_overrides.clear()


def add_profile(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            Profile(
                resume="dev",
                work_modes=["remote"],
                accepted_cities=["Maceió"],
                excluded_title_words=["estágio"],
            )
        )
        session.commit()


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_list_returns_newest_first_with_preview(client: TestClient) -> None:
    response = client.get("/jobs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    # Undated job goes last
    assert [item["id"] for item in body["items"]] == ["gupy:1", "gupy:2", "remotive:1", "gupy:3"]
    first = body["items"][0]
    assert "description" not in first
    assert first["description_preview"].endswith("...")
    assert len(first["description_preview"]) <= 283


def test_pagination(client: TestClient) -> None:
    body = client.get("/jobs", params={"limit": 2, "offset": 2}).json()

    assert body["total"] == 4
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert [item["id"] for item in body["items"]] == ["remotive:1", "gupy:3"]


@pytest.mark.parametrize(
    ("params", "expected_ids"),
    [
        ({"source": "remotive"}, ["remotive:1"]),
        ({"remote": "false"}, ["gupy:3"]),
        ({"q": "react"}, ["remotive:1"]),  # case-insensitive, title
        ({"q": "globex"}, ["remotive:1"]),  # company
        ({"source": "gupy", "remote": "true"}, ["gupy:1", "gupy:2"]),
    ],
)
def test_filters(client: TestClient, params: dict[str, str], expected_ids: list[str]) -> None:
    body = client.get("/jobs", params=params).json()

    assert [item["id"] for item in body["items"]] == expected_ids
    assert body["total"] == len(expected_ids)


def test_prefiltered_applies_the_profile(client: TestClient, engine: Engine) -> None:
    add_profile(engine)

    body = client.get("/jobs", params={"prefiltered": "true"}).json()

    # "Estágio" dropped by title, the São Paulo onsite job dropped by work mode
    assert [item["id"] for item in body["items"]] == ["gupy:1", "remotive:1"]
    assert body["total"] == 2


def test_prefiltered_without_profile_is_a_conflict(client: TestClient) -> None:
    response = client.get("/jobs", params={"prefiltered": "true"})

    assert response.status_code == 409


def test_invalid_limit_is_rejected(client: TestClient) -> None:
    assert client.get("/jobs", params={"limit": 500}).status_code == 422


def test_detail_returns_full_description(client: TestClient) -> None:
    response = client.get("/jobs/gupy:1")  # the ":" in the id is fine in a URL path

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Desenvolvedor .NET Pleno"
    assert body["description"] == "word " * 100


def test_detail_not_found(client: TestClient) -> None:
    response = client.get("/jobs/gupy:999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}


def test_cors_allows_only_the_local_frontend(client: TestClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET"}

    allowed = client.options("/jobs", headers={"Origin": "http://localhost:5173", **preflight})
    blocked = client.options("/jobs", headers={"Origin": "https://evil.example", **preflight})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers
