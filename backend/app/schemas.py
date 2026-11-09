"""API input/output models. Kept apart from the tables so the API contract
doesn't change by accident when a column is added (like DTOs vs entities)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import SQLModel

from app.models import Application, ApplicationStatus, Job, StatusChange

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


def column_values(row: SQLModel) -> dict[str, Any]:
    """Every field of a table row as a dict.

    Why not row.model_dump()? After session.commit() SQLAlchemy "expires" the
    object, and model_dump() reads the empty internal state without reloading
    it. getattr() goes through normal attribute access, which reloads it.
    """
    return {name: getattr(row, name) for name in type(row).model_fields}


def to_summary(job: Job) -> JobSummary:
    # Fields JobSummary doesn't declare (the full description) are ignored by Pydantic
    return JobSummary.model_validate(
        {**column_values(job), "description_preview": make_preview(job.description)}
    )


def to_detail(job: Job) -> JobDetail:
    return JobDetail.model_validate(
        {**column_values(job), "description_preview": make_preview(job.description)}
    )


# --- Applications -------------------------------------------------------------

NOTES_MAX_CHARS = 10_000  # "_" in numbers is just a visual separator, like 10_000 in C#


class ApplicationCreate(BaseModel):
    job_id: str
    # Typed as the enum: "aplicado" or any unknown value is rejected with 422
    status: ApplicationStatus = ApplicationStatus.INTERESTED
    notes: str = Field(default="", max_length=NOTES_MAX_CHARS)


class StatusUpdate(BaseModel):
    status: ApplicationStatus


class NotesUpdate(BaseModel):
    notes: str = Field(max_length=NOTES_MAX_CHARS)


class StatusChangeRead(BaseModel):
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_at: datetime


class ApplicationRead(BaseModel):
    """An application as a kanban card: its own fields plus a summary of the job."""

    id: int
    status: ApplicationStatus
    notes: str
    created_at: datetime
    updated_at: datetime
    job: JobSummary


class ApplicationDetail(ApplicationRead):
    history: list[StatusChangeRead]


def to_application_read(application: Application, job: Job) -> ApplicationRead:
    return ApplicationRead.model_validate({**column_values(application), "job": to_summary(job)})


def to_application_detail(
    application: Application, job: Job, history: list[StatusChange]
) -> ApplicationDetail:
    return ApplicationDetail.model_validate(
        {
            **column_values(application),
            "job": to_summary(job),
            "history": [column_values(change) for change in history],
        }
    )
