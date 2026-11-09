import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.sources import gupy
from app.sources.gupy import GUPY_URL, PAGE_SIZE, fetch_gupy_jobs

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "gupy_response.json"


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """autouse=True: applies to every test in this file, so no test actually sleeps."""
    monkeypatch.setattr(gupy, "DELAY_BETWEEN_REQUESTS_SECONDS", 0)


@pytest.fixture
def gupy_payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def make_raw_job(job_id: int) -> dict[str, Any]:
    return {
        "id": job_id,
        "name": f"Dev {job_id}",
        "careerPageName": "Acme",
        "jobUrl": f"https://acme.gupy.io/job/{job_id}",
        "workplaceType": "remote",
    }


def page_response(job_ids: range | list[int]) -> httpx.Response:
    return httpx.Response(200, json={"data": [make_raw_job(i) for i in job_ids]})


@respx.mock
def test_maps_jobs_and_skips_invalid_ones(gupy_payload: dict[str, Any]) -> None:
    route = respx.get(GUPY_URL).mock(return_value=httpx.Response(200, json=gupy_payload))

    with httpx.Client() as client:
        jobs = fetch_gupy_jobs(client, search_terms=["desenvolvedor"])

    params = route.calls.last.request.url.params
    assert params["jobName"] == "desenvolvedor"
    assert params["offset"] == "0"
    assert params["limit"] == str(PAGE_SIZE)

    assert [job.id for job in jobs] == ["gupy:2001", "gupy:2002", "gupy:2003"]
    remote_job, hybrid_job, unknown_job = jobs  # unpacking, like JS destructuring

    assert remote_job.title == "Desenvolvedor Full Stack Pleno | .NET e React"
    assert remote_job.company == "Empresa Exemplo"
    assert remote_job.url == "https://exemplo.gupy.io/job/abc?jobBoardSource=gupy_portal"
    assert remote_job.remote is True
    assert remote_job.location is None
    assert remote_job.description == "Sobre a vaga\nVocê vai trabalhar com C# & React.\n- APIs REST"
    assert remote_job.published_at == datetime(2026, 11, 9, 13, 6, 48, 690000, tzinfo=UTC)

    assert hybrid_job.remote is False
    assert hybrid_job.location == "Jundiaí - São Paulo"

    assert unknown_job.remote is None  # "flex" is not a known workplaceType
    assert unknown_job.location == "Alagoas"
    assert unknown_job.published_at is None


@respx.mock
def test_paginates_until_a_short_page() -> None:
    # side_effect lets the mock answer differently depending on the request
    def respond(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        if offset == 0:
            return page_response(range(1, PAGE_SIZE + 1))  # full page: keep going
        return page_response([PAGE_SIZE + 1, PAGE_SIZE + 2])  # short page: stop

    route = respx.get(GUPY_URL).mock(side_effect=respond)

    with httpx.Client() as client:
        jobs = fetch_gupy_jobs(client, search_terms=["dev"])

    assert route.call_count == 2
    assert len(jobs) == PAGE_SIZE + 2


@respx.mock
def test_stops_at_max_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gupy, "MAX_PAGES_PER_TERM", 3)

    def always_full_page(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return page_response(range(offset, offset + PAGE_SIZE))

    route = respx.get(GUPY_URL).mock(side_effect=always_full_page)

    with httpx.Client() as client:
        fetch_gupy_jobs(client, search_terms=["dev"])

    assert route.call_count == 3  # every page was full, but the cap stopped it


@respx.mock
def test_removes_duplicates_across_terms() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params["jobName"] == "backend":
            return page_response([1, 2])
        return page_response([2, 3])  # job 2 shows up in both searches

    respx.get(GUPY_URL).mock(side_effect=respond)

    with httpx.Client() as client:
        jobs = fetch_gupy_jobs(client, search_terms=["backend", "developer"])

    assert [job.id for job in jobs] == ["gupy:1", "gupy:2", "gupy:3"]


@respx.mock
def test_raises_when_api_returns_error() -> None:
    respx.get(GUPY_URL).mock(return_value=httpx.Response(503))

    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_gupy_jobs(client, search_terms=["dev"])


@respx.mock
def test_raises_when_response_format_changes() -> None:
    respx.get(GUPY_URL).mock(return_value=httpx.Response(200, json={"jobs": []}))

    with httpx.Client() as client, pytest.raises(ValueError, match="no 'data' list"):
        fetch_gupy_jobs(client, search_terms=["dev"])


def test_uses_search_terms_from_settings_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_terms: list[str] = []

    def fake_fetch_term(client: httpx.Client, term: str) -> list[dict[str, Any]]:
        requested_terms.append(term)
        return []

    monkeypatch.setattr(gupy, "fetch_term", fake_fetch_term)

    with httpx.Client() as client:
        fetch_gupy_jobs(client)

    assert requested_terms == gupy.get_settings().gupy_search_terms
