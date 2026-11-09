from typing import Any

from fastapi.testclient import TestClient


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body = {"provider": "greenhouse", "slug": "acme", "name": "Acme"}
    body.update(overrides)
    response = client.post("/companies", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list(client: TestClient) -> None:
    created = create(client, slug=" ACME ", name=" Acme Inc ")

    assert created["slug"] == "acme"  # normalized by add_company
    assert created["name"] == "Acme Inc"
    assert created["active"] is True
    assert [company["slug"] for company in client.get("/companies").json()] == ["acme"]


def test_duplicate_is_409(client: TestClient) -> None:
    create(client)

    response = client.post(
        "/companies", json={"provider": "greenhouse", "slug": "acme", "name": "Again"}
    )

    assert response.status_code == 409
    assert "already being watched" in response.json()["detail"]


def test_unknown_provider_is_422(client: TestClient) -> None:
    response = client.post("/companies", json={"provider": "workday", "slug": "x", "name": "X"})

    assert response.status_code == 422


def test_patch_only_changes_fields_sent(client: TestClient) -> None:
    company = create(client)

    paused = client.patch(f"/companies/{company['id']}", json={"active": False}).json()
    renamed = client.patch(f"/companies/{company['id']}", json={"name": "Acme Corp"}).json()

    assert paused["active"] is False
    assert paused["name"] == "Acme"  # untouched by the first PATCH
    assert renamed["name"] == "Acme Corp"
    assert renamed["active"] is False  # untouched by the second PATCH


def test_delete(client: TestClient) -> None:
    company = create(client)

    response = client.delete(f"/companies/{company['id']}")

    assert response.status_code == 204
    assert client.get("/companies").json() == []
    assert client.delete(f"/companies/{company['id']}").status_code == 404


def test_patch_unknown_company_is_404(client: TestClient) -> None:
    assert client.patch("/companies/999", json={"active": False}).status_code == 404
