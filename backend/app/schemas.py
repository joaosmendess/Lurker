"""API input/output models. Kept apart from the tables so the API contract
doesn't change by accident when a column is added (like DTOs vs entities)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import SQLModel

from app.models import Application, ApplicationStatus, Job, Profile, StatusChange, WatchedCompany
from app.profile import ProfileData

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
    tags: list[str] = []
    # The application for this job, if I already triaged it (None = not triaged yet)
    application_id: int | None = None
    application_status: ApplicationStatus | None = None


class JobDetail(JobSummary):
    """A single job, with the full description. Inherits every JobSummary field."""

    description: str


class JobPage(BaseModel):
    """One page of results plus what the UI needs to paginate."""

    items: list[JobSummary]
    total: int
    limit: int
    offset: int


class TagCount(BaseModel):
    tag: str
    count: int


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


def job_values(job: Job, application: Application | None) -> dict[str, Any]:
    """Job columns plus the computed fields shared by JobSummary and JobDetail."""
    return {
        **column_values(job),
        "description_preview": make_preview(job.description),
        "application_id": application.id if application else None,
        "application_status": application.status if application else None,
    }


def to_summary(job: Job, application: Application | None = None) -> JobSummary:
    # Fields JobSummary doesn't declare (the full description) are ignored by Pydantic
    return JobSummary.model_validate(job_values(job, application))


def to_detail(job: Job, application: Application | None = None) -> JobDetail:
    return JobDetail.model_validate(job_values(job, application))


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
    return ApplicationRead.model_validate(
        {**column_values(application), "job": to_summary(job, application)}
    )


def to_application_detail(
    application: Application, job: Job, history: list[StatusChange]
) -> ApplicationDetail:
    return ApplicationDetail.model_validate(
        {
            **column_values(application),
            "job": to_summary(job, application),
            "history": [column_values(change) for change in history],
        }
    )


# --- Profile ------------------------------------------------------------------


class ProfileRead(ProfileData):
    """The saved profile: the same fields accepted by PUT /profile, plus updated_at."""

    updated_at: datetime


def to_profile_read(profile: Profile) -> ProfileRead:
    return ProfileRead.model_validate(column_values(profile))


# --- Watched companies --------------------------------------------------------

type Provider = Literal["greenhouse", "lever"]


class CompanyCreate(BaseModel):
    provider: Provider
    slug: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class CompanyUpdate(BaseModel):
    """Partial update: only the fields sent are changed (None = keep as is)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None


class CompanyRead(BaseModel):
    id: int
    provider: str
    slug: str
    name: str
    active: bool
    created_at: datetime


def to_company_read(company: WatchedCompany) -> CompanyRead:
    return CompanyRead.model_validate(column_values(company))
