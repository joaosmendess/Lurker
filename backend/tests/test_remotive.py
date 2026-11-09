import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.sources.remotive import REMOTIVE_URL, fetch_remotive_jobs

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "remotive_response.json"


@pytest.fixture
def remotive_payload() -> dict[str, Any]:
    """Fixture: pytest injects this into any test that has a parameter with the same name."""
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# @respx.mock intercepts every httpx request made inside the test; nothing reaches
# the network. A request to an unmocked URL fails the test.
@respx.mock
def test_maps_valid_jobs_and_skips_invalid_ones(remotive_payload: dict[str, Any]) -> None:
    route = respx.get(REMOTIVE_URL).mock(return_value=httpx.Response(200, json=remotive_payload))

    with httpx.Client() as client:
        jobs = fetch_remotive_jobs(client)

    assert route.called
    assert route.calls.last.request.url.params["category"] == "software-dev"

    assert len(jobs) == 1  # the item without title was skipped
    job = jobs[0]
    assert job.id == "remotive:1001"
    assert job.source == "remotive"
    assert job.title == "Senior Backend Engineer"  # stripped
    assert job.company == "Acme Corp"
    assert job.url == "https://remotive.com/remote-jobs/software-dev/senior-backend-engineer-1001"
    assert job.location == "Worldwide"
    assert job.remote is True
    assert job.published_at == datetime(2026, 11, 7, 1, 10, 55, tzinfo=UTC)
    # Adjacent string literals are joined at compile time (no "+" needed)
    expected_description = (
        "We build tools for R&D teams.\n"  # entity decoded, <script> dropped
        "- 5+ years with Python\n"  # <li><p> without a lone bullet
        "- APIs and SQL"  # whitespace collapsed
    )
    assert job.description == expected_description


@respx.mock
def test_raises_when_api_returns_error() -> None:
    respx.get(REMOTIVE_URL).mock(return_value=httpx.Response(500))

    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_remotive_jobs(client)


@respx.mock
def test_raises_when_api_is_unreachable() -> None:
    respx.get(REMOTIVE_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    with httpx.Client() as client, pytest.raises(httpx.ConnectTimeout):
        fetch_remotive_jobs(client)


@respx.mock
def test_raises_when_response_format_changes() -> None:
    respx.get(REMOTIVE_URL).mock(return_value=httpx.Response(200, json={"results": []}))

    with httpx.Client() as client, pytest.raises(ValueError, match="no 'jobs' key"):
        fetch_remotive_jobs(client)
