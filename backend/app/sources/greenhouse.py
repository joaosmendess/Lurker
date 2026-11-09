"""Greenhouse source: public job board API, one board per company.

Docs: https://developers.greenhouse.io/job-board.html
"""

import html
import logging
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.models import Job
from app.sources.base import REQUEST_TIMEOUT_SECONDS, as_utc, html_to_text

SOURCE_NAME = "greenhouse"
BOARD_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

logger = logging.getLogger(__name__)


class GreenhouseLocation(BaseModel):
    name: str = ""


class GreenhouseJob(BaseModel):
    """Shape of one item in the board's "jobs" array (only the fields we use)."""

    id: int
    title: str
    absolute_url: str
    company_name: str | None = None
    location: GreenhouseLocation | None = None
    first_published: datetime | None = None
    updated_at: datetime | None = None
    content: str = ""


# The "*" makes every parameter after it keyword-only: callers must write
# slug="gitlab", never pass it by position. That's what lets collect.py
# pre-fill them with functools.partial and get a plain JobSource back.
def fetch_greenhouse_jobs(client: httpx.Client, *, slug: str, company_name: str) -> list[Job]:
    """Fetch every job of one company's board. Raises on network/HTTP/format errors."""
    response = client.get(
        BOARD_URL.format(slug=slug),
        params={"content": "true"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()  # unknown slug -> 404 -> HTTPStatusError

    payload: dict[str, Any] = response.json()
    if not isinstance(payload.get("jobs"), list):
        raise ValueError("Greenhouse response has no 'jobs' list; the format may have changed")

    jobs: list[Job] = []
    for raw_job in payload["jobs"]:
        try:
            greenhouse_job = GreenhouseJob.model_validate(raw_job)
        except ValidationError as error:
            logger.warning(
                "Skipping invalid Greenhouse job %s id=%s: %s", slug, raw_job.get("id"), error
            )
            continue
        jobs.append(to_job(greenhouse_job, slug=slug, company_name=company_name))

    logger.info("Greenhouse %s returned %d jobs", slug, len(jobs))
    return jobs


def to_job(greenhouse_job: GreenhouseJob, *, slug: str, company_name: str) -> Job:
    """Map a Greenhouse item to our normalized Job."""
    location = greenhouse_job.location.name.strip() if greenhouse_job.location else ""
    return Job(
        id=f"{SOURCE_NAME}:{slug}:{greenhouse_job.id}",
        source=SOURCE_NAME,
        title=greenhouse_job.title.strip(),
        company=greenhouse_job.company_name or company_name,
        url=greenhouse_job.absolute_url,
        location=location or None,
        remote=remote_from_location(location),
        description=content_to_text(greenhouse_job.content),
        published_at=as_utc(greenhouse_job.first_published or greenhouse_job.updated_at),
    )


def content_to_text(content: str) -> str:
    """Greenhouse escapes its HTML ("&lt;p&gt;"), so unescape it before stripping tags."""
    return html_to_text(html.unescape(content))


def remote_from_location(location: str) -> bool | None:
    """Greenhouse has no remote flag; "Remote, Brazil" in the location is the only hint.

    Returns None (unknown) instead of False when the word is missing: many boards
    just write a city even for remote roles.
    """
    lowered = location.lower()
    if "remote" in lowered or "remoto" in lowered:
        return True
    return None
