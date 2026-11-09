"""Database tables (SQLModel). Each class with table=True becomes a table."""

from datetime import UTC, datetime

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
