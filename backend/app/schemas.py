"""API input/output models. Kept apart from the tables so the API contract
doesn't change by accident when a column is added (like DTOs vs entities)."""

from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlmodel import SQLModel

from app.companies import CompanyStats, parse_board_url
from app.models import (
    Application,
    ApplicationStatus,
    Job,
    JobAnalysis,
    Profile,
    StatusChange,
    WatchedCompany,
)
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
    # The AI fit score, 0-100 (None = not analyzed yet)
    score: int | None = None


class AnalysisRead(BaseModel):
    score: int
    summary: str
    matches: list[str]
    gaps: list[str]
    red_flags: list[str]
    pitch: str
    pitch_warnings: list[str]
    model: str
    analyzed_at: datetime


class JobDetail(JobSummary):
    """A single job, with the full description. Inherits every JobSummary field."""

    description: str
    analysis: AnalysisRead | None = None


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


def job_values(
    job: Job, application: Application | None, analysis: JobAnalysis | None
) -> dict[str, Any]:
    """Job columns plus the computed fields shared by JobSummary and JobDetail."""
    return {
        **column_values(job),
        "description_preview": make_preview(job.description),
        "application_id": application.id if application else None,
        "application_status": application.status if application else None,
        "score": analysis.score if analysis else None,
    }


def to_summary(
    job: Job, application: Application | None = None, analysis: JobAnalysis | None = None
) -> JobSummary:
    # Fields JobSummary doesn't declare (the full description) are ignored by Pydantic
    return JobSummary.model_validate(job_values(job, application, analysis))


def to_detail(
    job: Job, application: Application | None = None, analysis: JobAnalysis | None = None
) -> JobDetail:
    values = job_values(job, application, analysis)
    values["analysis"] = column_values(analysis) if analysis else None
    return JobDetail.model_validate(values)


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


# --- Tailored resume -----------------------------------------------------------


class TailoredResumeRead(BaseModel):
    job_id: str
    content: str
    changes: list[str]
    missing: list[str]
    warnings: list[str]
    model: str
    created_at: datetime


class LLMStatus(BaseModel):
    configured: bool
    has_key: bool
    model: str
    base_url: str


# --- Watched companies --------------------------------------------------------

type Provider = Literal["greenhouse", "lever"]


class CompanyCreate(BaseModel):
    """A board to watch: provider + slug, or a pasted link in "slug" (provider then optional)."""

    # Strips every str field before the length checks, so "  " fails min_length
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Provider
    # Only URL-safe characters: the slug goes straight into the board's URL
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    name: str = Field(min_length=1, max_length=200)

    # mode="before": runs on the raw JSON dict, before any field is validated.
    # That's what lets a link fill in two fields (provider and slug) at once.
    @model_validator(mode="before")
    @classmethod
    def read_board_link(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("slug"), str):
            return data  # let the normal validation report what's wrong
        data = dict(data)  # copy: never change the caller's dict
        parsed = parse_board_url(data["slug"])
        if parsed is not None:
            data["provider"], data["slug"] = parsed
        else:
            data["slug"] = data["slug"].strip().lower()
        return data


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
    job_count: int = 0
    to_triage: int = 0
    failed_last_collect: bool = False


class CompanyCreated(CompanyRead):
    found_jobs: int  # open jobs on the board when it was added
    saved_jobs: int  # of those, how many were new


def to_company_read(company: WatchedCompany, stats: CompanyStats | None = None) -> CompanyRead:
    stats = stats or CompanyStats()
    # asdict turns the dataclass into a dict; ** merges it with the columns
    return CompanyRead.model_validate({**column_values(company), **asdict(stats)})
