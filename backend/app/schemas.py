"""API input/output models. Kept apart from the tables so the API contract
doesn't change by accident when a column is added (like DTOs vs entities)."""

from datetime import datetime

from pydantic import BaseModel

from app.models import Job

DESCRIPTION_PREVIEW_CHARS = 280


class JobSummary(BaseModel):
    """A job in a list: everything except the full description."""

    id: str
    source: str
    title: str
    company: str
    url: str
    location: str | None
    remote: bool | None
    published_at: datetime | None
    collected_at: datetime
    description_preview: str


class JobDetail(JobSummary):
    """A single job, with the full description. Inherits every JobSummary field."""

    description: str


class JobPage(BaseModel):
    """One page of results plus what the UI needs to paginate."""

    items: list[JobSummary]
    total: int
    limit: int
    offset: int


def make_preview(description: str) -> str:
    """First characters of the description, cut at a word boundary."""
    flat = " ".join(description.split())
    if len(flat) <= DESCRIPTION_PREVIEW_CHARS:
        return flat
    # rsplit(" ", 1) splits once from the right: drops the half-cut last word
    cut = flat[:DESCRIPTION_PREVIEW_CHARS].rsplit(" ", 1)[0]
    return f"{cut}..."


def to_summary(job: Job) -> JobSummary:
    # model_dump() gives every column as a dict; fields JobSummary doesn't
    # declare (the full description) are ignored by Pydantic
    return JobSummary.model_validate(
        {**job.model_dump(), "description_preview": make_preview(job.description)}
    )


def to_detail(job: Job) -> JobDetail:
    return JobDetail.model_validate(
        {**job.model_dump(), "description_preview": make_preview(job.description)}
    )
