from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models import CollectRun

type FakeWeb = dict[str, httpx.Response]


def greenhouse_board(fake_web: FakeWeb, slug: str, titles: list[str]) -> None:
    """Publish a fake Greenhouse board with one job per title."""
    jobs = [
        {
            "id": number,
            "title": title,
            "absolute_url": f"https://job-boards.greenhouse.io/{slug}/jobs/{number}",
            "location": {"name": "Remote, Brazil"},
            "content": "&lt;p&gt;Python and React&lt;/p&gt;",
        }
        for number, title in enumerate(titles, start=1)
    ]
    fake_web[f"/v1/boards/{slug}/jobs"] = httpx.Response(200, json={"jobs": jobs})


def create(client: TestClient, fake_web: FakeWeb, **overrides: Any) -> dict[str, Any]:
    greenhouse_board(fake_web, "acme", ["Backend Developer", "Frontend Developer"])
    body = {"provider": "greenhouse", "slug": "acme", "name": "Acme"}
    body.update(overrides)
    response = client.post("/companies", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_checks_board_and_saves_its_jobs(client: TestClient, fake_web: FakeWeb) -> None:
    created = create(client, fake_web, slug=" ACME ", name=" Acme Inc ")

    assert created["slug"] == "acme"  # normalized before the request
    assert created["name"] == "Acme Inc"
    assert created["active"] is True
    assert (created["found_jobs"], created["saved_jobs"]) == (2, 2)
    assert created["job_count"] == 2

    jobs = client.get("/jobs").json()["items"]
    assert {job["id"] for job in jobs} == {"greenhouse:acme:1", "greenhouse:acme:2"}
    assert {"Python", "React"} <= set(jobs[0]["tags"])  # tagged like in a collection


@pytest.mark.parametrize(
    "link",
    [
        "https://job-boards.greenhouse.io/acme",
        "https://boards.greenhouse.io/acme/jobs/123?gh_src=x",
        "boards.greenhouse.io/embed/job_board?for=acme",
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
    ],
)
def test_create_from_pasted_greenhouse_link(
    client: TestClient, fake_web: FakeWeb, link: str
) -> None:
    greenhouse_board(fake_web, "acme", ["Developer"])

    # No provider: the link says which one it is
    response = client.post("/companies", json={"slug": link, "name": "Acme"})

    assert response.status_code == 201, response.text
    assert (response.json()["provider"], response.json()["slug"]) == ("greenhouse", "acme")


def test_create_from_pasted_lever_link(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web["/v0/postings/acme"] = httpx.Response(200, json=[])

    response = client.post("/companies", json={"slug": "jobs.lever.co/acme/abc-123", "name": "A"})

    assert response.status_code == 201, response.text
    assert (response.json()["provider"], response.json()["slug"]) == ("lever", "acme")
    assert response.json()["found_jobs"] == 0


def test_board_that_does_not_exist_is_422_and_not_saved(
    client: TestClient, fake_web: FakeWeb
) -> None:
    fake_web["/v1/boards/typo/jobs"] = httpx.Response(404, json={"status": 404})

    response = client.post(
        "/companies", json={"provider": "greenhouse", "slug": "typo", "name": "Typo"}
    )

    assert response.status_code == 422
    assert "No public greenhouse board" in response.json()["detail"]
    assert client.get("/companies").json() == []


def test_board_site_down_is_502_and_not_saved(client: TestClient, fake_web: FakeWeb) -> None:
    fake_web["/v1/boards/acme/jobs"] = httpx.Response(503)

    response = client.post(
        "/companies", json={"provider": "greenhouse", "slug": "acme", "name": "Acme"}
    )

    assert response.status_code == 502
    assert client.get("/companies").json() == []


def test_duplicate_is_409_without_fetching_the_board(client: TestClient, fake_web: FakeWeb) -> None:
    create(client, fake_web)
    fake_web.clear()  # any request now fails the test

    response = client.post(
        "/companies", json={"provider": "greenhouse", "slug": "acme", "name": "Again"}
    )

    assert response.status_code == 409
    assert "already being watched" in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"provider": "workday", "slug": "x", "name": "X"},  # unsupported provider
        {"provider": "greenhouse", "slug": "../admin", "name": "X"},  # not a URL-safe slug
        {"provider": "greenhouse", "slug": "acme", "name": "   "},  # blank name
        {"slug": "acme", "name": "Acme"},  # bare slug and no provider
        {"slug": "https://example.com/acme", "name": "Acme"},  # link to an unknown site
    ],
)
def test_invalid_body_is_422_without_network(client: TestClient, body: dict[str, Any]) -> None:
    assert client.post("/companies", json=body).status_code == 422


def test_list_counts_jobs_to_triage_and_failures(
    client: TestClient, fake_web: FakeWeb, engine: Engine
) -> None:
    create(client, fake_web)
    client.post("/applications", json={"job_id": "greenhouse:acme:1", "status": "discarded"})
    with Session(engine) as session:
        session.add(CollectRun(failed_sources=["greenhouse:acme"]))
        session.commit()

    [company] = client.get("/companies").json()

    assert company["job_count"] == 2
    assert company["to_triage"] == 1  # the discarded one no longer counts
    assert company["failed_last_collect"] is True


def test_patch_only_changes_fields_sent(client: TestClient, fake_web: FakeWeb) -> None:
    company = create(client, fake_web)

    paused = client.patch(f"/companies/{company['id']}", json={"active": False}).json()
    renamed = client.patch(f"/companies/{company['id']}", json={"name": "Acme Corp"}).json()

    assert paused["active"] is False
    assert paused["name"] == "Acme"  # untouched by the first PATCH
    assert paused["job_count"] == 2  # stats come back on PATCH too
    assert renamed["name"] == "Acme Corp"
    assert renamed["active"] is False  # untouched by the second PATCH


def test_delete_keeps_collected_jobs(client: TestClient, fake_web: FakeWeb) -> None:
    company = create(client, fake_web)

    response = client.delete(f"/companies/{company['id']}")

    assert response.status_code == 204
    assert client.get("/companies").json() == []
    assert client.get("/jobs").json()["total"] == 2
    assert client.delete(f"/companies/{company['id']}").status_code == 404


def test_patch_unknown_company_is_404(client: TestClient) -> None:
    assert client.patch("/companies/999", json={"active": False}).status_code == 404


def test_jobs_can_be_filtered_by_one_company_board(client: TestClient, fake_web: FakeWeb) -> None:
    create(client, fake_web)  # acme: 2 jobs
    greenhouse_board(fake_web, "acmecorp", ["Data Engineer"])
    client.post("/companies", json={"provider": "greenhouse", "slug": "acmecorp", "name": "Corp"})

    def total(source: str) -> int:
        return client.get("/jobs", params={"source": source}).json()["total"]

    assert total("greenhouse") == 3
    assert total("greenhouse:acme") == 2  # not acmecorp: the id prefix ends at ":"
    assert total("greenhouse:acmecorp") == 1
    assert total("greenhouse:ac") == 0
