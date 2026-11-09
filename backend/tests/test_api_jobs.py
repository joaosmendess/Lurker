from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db import build_engine, init_db
from app.models import Profile
from tests.conftest import make_job


# Same name as the conftest fixture: this module's version wins here, and the
# shared "client" fixture picks it up automatically (fixture overriding).
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


def test_jobs_carry_their_application_status(client: TestClient) -> None:
    client.post("/applications", json={"job_id": "gupy:1", "status": "discarded"})

    items = {item["id"]: item for item in client.get("/jobs").json()["items"]}
    detail = client.get("/jobs/gupy:1").json()

    assert items["gupy:1"]["application_status"] == "discarded"
    assert items["gupy:1"]["application_id"] is not None
    assert items["gupy:2"]["application_status"] is None
    assert detail["application_status"] == "discarded"


def test_untriaged_hides_jobs_with_an_application(client: TestClient, engine: Engine) -> None:
    add_profile(engine)
    client.post("/applications", json={"job_id": "gupy:1"})

    body = client.get("/jobs", params={"untriaged": "true", "prefiltered": "true"}).json()

    # gupy:1 now has an application; gupy:2 and gupy:3 are dropped by the pre-filter
    assert [item["id"] for item in body["items"]] == ["remotive:1"]
    assert body["total"] == 1


def test_deleting_the_application_makes_the_job_untriaged_again(client: TestClient) -> None:
    application = client.post("/applications", json={"job_id": "gupy:1"}).json()

    response = client.delete(f"/applications/{application['id']}")

    assert response.status_code == 204
    untriaged = client.get("/jobs", params={"untriaged": "true"}).json()
    assert "gupy:1" in [item["id"] for item in untriaged["items"]]
    assert client.get(f"/applications/{application['id']}").status_code == 404


def test_cors_allows_only_the_local_frontend(client: TestClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET"}

    allowed = client.options("/jobs", headers={"Origin": "http://localhost:5173", **preflight})
    blocked = client.options("/jobs", headers={"Origin": "https://evil.example", **preflight})

    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers
