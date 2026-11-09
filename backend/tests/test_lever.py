import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.sources.lever import fetch_lever_jobs

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "lever_postings.json"
ACME_URL = "https://api.lever.co/v0/postings/acme"


@pytest.fixture
def postings_payload() -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@respx.mock
def test_maps_postings_and_skips_invalid_ones(postings_payload: list[dict[str, Any]]) -> None:
    route = respx.get(ACME_URL).mock(return_value=httpx.Response(200, json=postings_payload))

    with httpx.Client() as client:
        jobs = fetch_lever_jobs(client, slug="acme", company_name="Acme")

    assert route.calls.last.request.url.params["mode"] == "json"
    assert [job.id for job in jobs] == [
        "lever:acme:6ed76ce8-4156-4b60-b120-403538bd66cd",
        "lever:acme:aaaa-bbbb",
    ]
    remote_job, onsite_job = jobs

    assert remote_job.source == "lever"
    assert remote_job.title == "Full Stack Developer"
    assert remote_job.company == "Acme"  # Lever doesn't send it; comes from WatchedCompany
    assert remote_job.url == "https://jobs.lever.co/acme/6ed76ce8-4156-4b60-b120-403538bd66cd"
    assert remote_job.location == "Brazil"
    assert remote_job.remote is True
    assert remote_job.published_at == datetime(2026, 8, 11, 17, 38, 11, 368000, tzinfo=UTC)
    expected_description = (
        "About us\n"
        "Requirements <must-have>\n"  # list title escaped, so it's not eaten as a tag
        "- 5+ years with C#\n"  # requirements from "lists" are included
        "- SQL Server\n"
        "We offer remote work."
    )
    assert remote_job.description == expected_description

    assert onsite_job.remote is False
    assert onsite_job.location == "New York, NY"
    assert onsite_job.published_at is None
    assert onsite_job.description == ""


@respx.mock
def test_raises_on_unknown_company() -> None:
    respx.get(ACME_URL).mock(return_value=httpx.Response(404, json={"ok": False}))

    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_lever_jobs(client, slug="acme", company_name="Acme")


@respx.mock
def test_raises_when_response_format_changes() -> None:
    respx.get(ACME_URL).mock(return_value=httpx.Response(200, json={"data": []}))

    with httpx.Client() as client, pytest.raises(ValueError, match="not a list"):
        fetch_lever_jobs(client, slug="acme", company_name="Acme")
