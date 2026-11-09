import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.sources.greenhouse import fetch_greenhouse_jobs, remote_from_location

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse_board.json"
ACME_URL = "https://boards-api.greenhouse.io/v1/boards/acme/jobs"


@pytest.fixture
def board_payload() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@respx.mock
def test_maps_jobs_and_skips_invalid_ones(board_payload: dict[str, Any]) -> None:
    route = respx.get(ACME_URL).mock(return_value=httpx.Response(200, json=board_payload))

    with httpx.Client() as client:
        jobs = fetch_greenhouse_jobs(client, slug="acme", company_name="Acme (watched)")

    assert route.calls.last.request.url.params["content"] == "true"
    assert [job.id for job in jobs] == ["greenhouse:acme:111", "greenhouse:acme:222"]
    remote_job, city_job = jobs

    assert remote_job.source == "greenhouse"
    assert remote_job.title == "Senior Backend Engineer"
    assert remote_job.company == "Acme Inc"  # from the payload
    assert remote_job.url == "https://job-boards.greenhouse.io/acme/jobs/111"
    assert remote_job.location == "Remote, Brazil"
    assert remote_job.remote is True
    # Double-escaped HTML was unescaped, then stripped: "&amp;amp;" -> "&amp;" -> "&"
    assert remote_job.description == "We build R&D tools.\n- Python"
    assert remote_job.published_at == datetime(2026, 7, 22, 17, 38, 40, tzinfo=UTC)

    assert city_job.company == "Acme (watched)"  # fallback when the payload has no name
    assert city_job.remote is None  # no "remote" in the location: unknown, not False
    assert city_job.published_at == datetime(2026, 11, 1, 13, 0, 0, tzinfo=UTC)  # updated_at


@respx.mock
def test_raises_on_unknown_board() -> None:
    respx.get(ACME_URL).mock(
        return_value=httpx.Response(404, json={"status": 404, "error": "Job not found"})
    )

    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_greenhouse_jobs(client, slug="acme", company_name="Acme")


@respx.mock
def test_raises_when_response_format_changes() -> None:
    respx.get(ACME_URL).mock(return_value=httpx.Response(200, json={"postings": []}))

    with httpx.Client() as client, pytest.raises(ValueError, match="no 'jobs' list"):
        fetch_greenhouse_jobs(client, slug="acme", company_name="Acme")


# parametrize runs the same test once per tuple, like [Theory] + [InlineData] in xUnit
@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Remote, Brazil", True),
        ("Brasil (Remoto)", True),
        ("REMOTE", True),
        ("São Paulo", None),
        ("", None),
    ],
)
def test_remote_from_location(location: str, expected: bool | None) -> None:
    assert remote_from_location(location) is expected
