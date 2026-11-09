"""Lever source: public postings API, one site per company.

Docs: https://github.com/lever/postings-api
"""

import html
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.models import Job
from app.sources.base import REQUEST_TIMEOUT_SECONDS, html_to_text

SOURCE_NAME = "lever"
POSTINGS_URL = "https://api.lever.co/v0/postings/{slug}"

REMOTE_BY_WORKPLACE_TYPE: dict[str, bool] = {
    "remote": True,
    "hybrid": False,
    "onsite": False,
}

logger = logging.getLogger(__name__)


class LeverCategories(BaseModel):
    location: str | None = None


class LeverList(BaseModel):
    """A titled section, e.g. "Requirements", whose content is a run of <li> items."""

    text: str = ""
    content: str = ""


class LeverPosting(BaseModel):
    """Shape of one posting (only the fields we use)."""

    model_config = ConfigDict(alias_generator=to_camel)  # hostedUrl -> hosted_url

    id: str
    text: str  # the job title
    hosted_url: str
    categories: LeverCategories = Field(default_factory=LeverCategories)
    workplace_type: str | None = None
    created_at: int | None = None  # milliseconds since 1970-01-01 UTC
    description: str = ""
    lists: list[LeverList] = Field(default_factory=list)
    additional: str = ""


def fetch_lever_jobs(client: httpx.Client, *, slug: str, company_name: str) -> list[Job]:
    """Fetch every posting of one company. Raises on network/HTTP/format errors."""
    response = client.get(
        POSTINGS_URL.format(slug=slug),
        params={"mode": "json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload: Any = response.json()
    # Unlike the other sources, Lever answers with a bare list
    if not isinstance(payload, list):
        raise ValueError("Lever response is not a list; the format may have changed")

    jobs: list[Job] = []
    for raw_posting in payload:
        try:
            posting = LeverPosting.model_validate(raw_posting)
        except ValidationError as error:
            logger.warning("Skipping invalid Lever posting %s: %s", slug, error)
            continue
        jobs.append(to_job(posting, slug=slug, company_name=company_name))

    logger.info("Lever %s returned %d jobs", slug, len(jobs))
    return jobs


def to_job(posting: LeverPosting, *, slug: str, company_name: str) -> Job:
    """Map a Lever posting to our normalized Job."""
    return Job(
        id=f"{SOURCE_NAME}:{slug}:{posting.id}",
        source=SOURCE_NAME,
        title=posting.text.strip(),
        company=company_name,  # not present in Lever's payload
        url=posting.hosted_url,
        location=posting.categories.location,
        remote=REMOTE_BY_WORKPLACE_TYPE.get(posting.workplace_type or ""),
        description=build_description(posting),
        published_at=from_epoch_millis(posting.created_at),
    )


def build_description(posting: LeverPosting) -> str:
    """Join intro, the titled lists (requirements live there) and the closing text."""
    html_parts: list[str] = [posting.description]
    for section in posting.lists:
        # The title is plain text: escape it so a "<" can't be read as a tag
        html_parts.append(f"<h3>{html.escape(section.text)}</h3><ul>{section.content}</ul>")
    html_parts.append(posting.additional)
    return html_to_text("".join(html_parts))


def from_epoch_millis(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC)
