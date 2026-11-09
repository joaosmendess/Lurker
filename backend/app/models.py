"""Database tables (SQLModel). Each class with table=True becomes a table."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Current time in UTC. All timestamps in the database are UTC."""
    return datetime.now(UTC)


class Job(SQLModel, table=True):
    """A job posting collected from a source, already normalized."""

    # Format "<source>:<original id>", e.g. "gupy:123" or "greenhouse:acme:456".
    # Prefixing with the source keeps ids unique across providers.
    id: str = Field(primary_key=True)
    source: str = Field(index=True)
    title: str
    company: str
    url: str
    location: str | None = None
    # None means "unknown": many sources don't say whether a job is remote
    remote: bool | None = None
    description: str = ""  # plain text, HTML already stripped
    published_at: datetime | None = None
    # default_factory runs on every new instance; a plain default would be
    # evaluated only once, when the class is defined
    collected_at: datetime = Field(default_factory=utc_now)


class WatchedCompany(SQLModel, table=True):
    """A company whose public job board (Greenhouse or Lever) we monitor."""

    # Class attribute read by SQLAlchemy: a company can't be added twice per provider
    __table_args__ = (UniqueConstraint("provider", "slug"),)

    # None until the database assigns it (autoincrement), like an int? Id in EF
    id: int | None = Field(default=None, primary_key=True)
    provider: str  # "greenhouse" or "lever"
    slug: str  # board name in the URL, e.g. "gitlab"
    name: str  # display name; Lever's API doesn't return it
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now)


PROFILE_ID = 1  # the profile is a single row; this is its fixed id


def json_list_column() -> Column:
    """A column that stores a Python list as JSON text (SQLite has no array type).

    Each field needs its own Column object, hence a function instead of a constant.
    """
    return Column(JSON, nullable=False)


class Profile(SQLModel, table=True):
    """My resume and job preferences, used by the pre-filter and the AI scoring.

    Note on JSON columns: SQLAlchemy doesn't notice in-place changes such as
    profile.accepted_cities.append(...). Always assign a new list instead.
    """

    id: int = Field(default=PROFILE_ID, primary_key=True)
    resume: str = ""
    # "remote" | "hybrid" | "onsite"
    work_modes: list[str] = Field(default_factory=list, sa_column=json_list_column())
    # Cities accepted for hybrid/onsite jobs, e.g. ["Maceió"]
    accepted_cities: list[str] = Field(default_factory=list, sa_column=json_list_column())
    # e.g. ["junior", "pleno"]; the AI uses this to judge seniority fit
    seniority_levels: list[str] = Field(default_factory=list, sa_column=json_list_column())
    # "clt" | "pj"
    contract_types: list[str] = Field(default_factory=list, sa_column=json_list_column())
    # Free text for the AI, e.g. "CLT: R$ 5.000 / PJ: R$ 4.000 a 6.000"
    salary_expectation: str = ""
    # Jobs whose title contains any of these words are dropped before the AI
    excluded_title_words: list[str] = Field(default_factory=list, sa_column=json_list_column())
    updated_at: datetime = Field(default_factory=utc_now)
