from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from tests.conftest import make_job


@pytest.fixture(autouse=True)
def seed_jobs(engine: Engine) -> None:
    with Session(engine) as session:
        session.add_all(
            [
                make_job("gupy:1", "Dev .NET"),
                make_job("gupy:2", "Dev React"),
                make_job("gupy:3", "Dev Python"),
            ]
        )
        session.commit()


def create(client: TestClient, job_id: str = "gupy:1", **body: Any) -> dict[str, Any]:
    response = client.post("/applications", json={"job_id": job_id, **body})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_defaults_to_interested_and_embeds_the_job(client: TestClient) -> None:
    application = create(client)

    assert application["status"] == "interested"
    assert application["notes"] == ""
    assert application["job"]["id"] == "gupy:1"
    assert application["job"]["title"] == "Dev .NET"


def test_create_can_discard_directly(client: TestClient) -> None:
    application = create(client, status="discarded")

    assert application["status"] == "discarded"


def test_create_for_unknown_job_is_404(client: TestClient) -> None:
    response = client.post("/applications", json={"job_id": "gupy:999"})

    assert response.status_code == 404


def test_second_application_for_same_job_is_409(client: TestClient) -> None:
    first = create(client)

    response = client.post("/applications", json={"job_id": "gupy:1"})

    assert response.status_code == 409
    assert str(first["id"]) in response.json()["detail"]


def test_invalid_status_is_422(client: TestClient) -> None:
    response = client.post("/applications", json={"job_id": "gupy:1", "status": "aplicado"})

    assert response.status_code == 422


def test_moving_records_history(client: TestClient) -> None:
    application = create(client)
    url = f"/applications/{application['id']}"

    client.patch(f"{url}/status", json={"status": "applied"})
    moved = client.patch(f"{url}/status", json={"status": "interview"}).json()
    detail = client.get(url).json()

    assert moved["status"] == "interview"
    assert moved["updated_at"] >= application["updated_at"]
    transitions = [(change["from_status"], change["to_status"]) for change in detail["history"]]
    assert transitions == [
        (None, "interested"),  # the creation itself
        ("interested", "applied"),
        ("applied", "interview"),
    ]


def test_moving_to_the_same_status_changes_nothing(client: TestClient) -> None:
    application = create(client)
    url = f"/applications/{application['id']}"

    response = client.patch(f"{url}/status", json={"status": "interested"})

    assert response.status_code == 200
    assert len(client.get(url).json()["history"]) == 1


def test_moving_back_is_allowed(client: TestClient) -> None:
    application = create(client, status="interview")
    url = f"/applications/{application['id']}"

    response = client.patch(f"{url}/status", json={"status": "applied"})

    assert response.json()["status"] == "applied"


def test_update_notes(client: TestClient) -> None:
    application = create(client)

    response = client.patch(
        f"/applications/{application['id']}", json={"notes": "Recrutadora: Ana"}
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Recrutadora: Ana"


def test_notes_have_a_size_limit(client: TestClient) -> None:
    application = create(client)

    response = client.patch(f"/applications/{application['id']}", json={"notes": "x" * 10_001})

    assert response.status_code == 422


def test_list_filters_by_status(client: TestClient) -> None:
    create(client, "gupy:1")
    create(client, "gupy:2", status="discarded")

    everything = client.get("/applications").json()
    discarded = client.get("/applications", params={"status": "discarded"}).json()

    assert len(everything) == 2
    assert [item["job"]["id"] for item in discarded] == ["gupy:2"]


def test_list_accepts_several_statuses(client: TestClient) -> None:
    create(client, "gupy:1")
    create(client, "gupy:2", status="discarded")
    create(client, "gupy:3", status="interview")

    # The kanban's request: every column except "discarded"
    board = client.get("/applications", params={"status": ["interested", "interview"]}).json()

    assert sorted(item["job"]["id"] for item in board) == ["gupy:1", "gupy:3"]


def test_list_rejects_unknown_status(client: TestClient) -> None:
    assert client.get("/applications", params={"status": "aplicada"}).status_code == 422


@pytest.mark.parametrize("method", ["get", "patch"])
def test_unknown_application_is_404(client: TestClient, method: str) -> None:
    # getattr(obj, "get") fetches the method by name, so one test covers both verbs
    request = getattr(client, method)
    kwargs = {"json": {"notes": "x"}} if method == "patch" else {}

    assert request("/applications/999", **kwargs).status_code == 404
