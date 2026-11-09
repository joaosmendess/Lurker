"""Remotive source: public, documented API with remote-only jobs.

Terms: at most ~4 requests/day and always link back to the Remotive URL.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.models import Job
from app.sources.base import REQUEST_TIMEOUT_SECONDS, html_to_text

SOURCE_NAME = "remotive"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"

# Like ILogger<T> in C#: the logger is named after the module ("app.sources.remotive")
logger = logging.getLogger(__name__)


class RemotiveJob(BaseModel):
    """Shape of one item in Remotive's "jobs" array (only the fields we use).

    Extra fields in the payload are ignored by default.
    """

    id: int
    url: str
    title: str
    company_name: str
    publication_date: datetime
    candidate_required_location: str = ""
    description: str = ""


def fetch_remotive_jobs(client: httpx.Client) -> list[Job]:
    """Fetch software-dev jobs from Remotive. Raises on network/HTTP/format errors."""
    response = client.get(
        REMOTIVE_URL,
        params={"category": "software-dev"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()  # 4xx/5xx -> httpx.HTTPStatusError

    payload: dict[str, Any] = response.json()
    if "jobs" not in payload:
        raise ValueError("Remotive response has no 'jobs' key; the format may have changed")

    jobs: list[Job] = []
    for raw_job in payload["jobs"]:
        try:
            remotive_job = RemotiveJob.model_validate(raw_job)
        except ValidationError as error:
            # One bad item shouldn't discard the other jobs of the batch
            logger.warning("Skipping invalid Remotive job id=%s: %s", raw_job.get("id"), error)
            continue
        jobs.append(to_job(remotive_job))

    logger.info("Remotive returned %d jobs", len(jobs))
    return jobs


def to_job(remotive_job: RemotiveJob) -> Job:
    """Map a Remotive item to our normalized Job."""
    return Job(
        id=f"{SOURCE_NAME}:{remotive_job.id}",
        source=SOURCE_NAME,
        title=remotive_job.title.strip(),
        company=remotive_job.company_name.strip(),
        url=remotive_job.url,
        # e.g. "Worldwide" or "USA": remote, but maybe not open to Brazil
        location=remotive_job.candidate_required_location or None,
        remote=True,  # Remotive only lists remote jobs
        description=html_to_text(remotive_job.description),
        published_at=as_utc(remotive_job.publication_date),
    )


def as_utc(value: datetime) -> datetime:
    """Remotive sends dates without timezone; we treat them as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
