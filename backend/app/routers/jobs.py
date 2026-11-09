"""Job routes: list (with filters and pagination), stack tag counts and detail."""

from collections import Counter
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast
from sqlmodel import Session, col, func, or_, select
from sqlmodel.sql.expression import Select

from app.db import get_session
from app.filters import filter_jobs
from app.models import Application, Job, JobAnalysis
from app.profile import get_profile
from app.schemas import JobDetail, JobPage, TagCount, to_detail, to_summary

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Annotated + Depends: FastAPI calls get_session() for each request and passes
# the result in. Same idea as constructor injection with a scoped DbContext in ASP.NET.
SessionDep = Annotated[Session, Depends(get_session)]

# Each result row is a (job, its application or None) tuple
type JobRow = tuple[Job, Application | None]


@dataclass(frozen=True)
class JobFilters:
    source: str | None
    remote: bool | None
    search: str | None
    prefiltered: bool
    untriaged: bool
    stack: list[str]


def job_filters(
    source: Annotated[
        str | None,
        Query(max_length=150, description='"greenhouse", or one board: "greenhouse:stone"'),
    ] = None,
    remote: bool | None = None,
    q: Annotated[str | None, Query(max_length=100, description="search in title/company")] = None,
    prefiltered: Annotated[
        bool, Query(description="only jobs that pass the profile pre-filter")
    ] = False,
    untriaged: Annotated[
        bool, Query(description="only jobs without an application (not triaged yet)")
    ] = False,
    stack: Annotated[
        list[str] | None,
        Query(description="repeatable: ?stack=React&stack=.NET (jobs with ANY of them)"),
    ] = None,
) -> JobFilters:
    """Query-string filters shared by several routes. Used as a dependency, so each
    route declares one parameter instead of repeating six (like a [FromQuery] model)."""
    return JobFilters(source, remote, q, prefiltered, untriaged, stack or [])


FiltersDep = Annotated[JobFilters, Depends(job_filters)]


def like_escape(value: str) -> str:
    """Make % and _ literal inside a LIKE pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_jobs_query(filters: JobFilters) -> Select[JobRow]:
    """SELECT jobs + their application (LEFT JOIN) with the SQL filters, newest first."""
    # outerjoin = LEFT JOIN: jobs without an application come back with None
    statement = select(Job, Application).outerjoin(
        Application, col(Application.job_id) == col(Job.id)
    )
    if filters.source is not None and ":" in filters.source:
        # One company's board, "greenhouse:stone": the prefix of its job ids
        statement = statement.where(
            col(Job.id).like(f"{like_escape(filters.source)}:%", escape="\\")
        )
    elif filters.source is not None:
        statement = statement.where(Job.source == filters.source)
    if filters.remote is not None:
        statement = statement.where(Job.remote == filters.remote)
    if filters.search:
        pattern = f"%{like_escape(filters.search.strip())}%"
        statement = statement.where(
            or_(
                col(Job.title).ilike(pattern, escape="\\"),
                col(Job.company).ilike(pattern, escape="\\"),
            )
        )
    if filters.untriaged:
        statement = statement.where(col(Application.id).is_(None))
    if filters.stack:
        # tags is stored as JSON text like ["React", ".NET"]; matching the quoted
        # tag keeps "React" from also matching "React Native"
        tags_text = cast(Job.tags, String)
        statement = statement.where(
            or_(*(tags_text.like(f'%"{like_escape(tag)}"%', escape="\\") for tag in filters.stack))
        )
    # Joined only to sort: best AI score first, then not-yet-analyzed jobs by date.
    # Jobs without a publish date go last; id breaks ties so pages are stable
    statement = statement.outerjoin(JobAnalysis, col(JobAnalysis.job_id) == col(Job.id))
    return statement.order_by(
        col(JobAnalysis.score).desc().nulls_last(),
        col(Job.published_at).desc().nulls_last(),
        col(Job.collected_at).desc(),
        col(Job.id),
    )


def analyses_for(session: Session, jobs: list[Job]) -> dict[str, JobAnalysis]:
    """The analyses of these jobs in one query (not one per job: no N+1)."""
    ids = [job.id for job in jobs]
    found = session.exec(select(JobAnalysis).where(col(JobAnalysis.job_id).in_(ids))).all()
    return {analysis.job_id: analysis for analysis in found}


def apply_profile_filter(session: Session, rows: list[JobRow]) -> list[JobRow]:
    """Keep the rows whose job passes the profile pre-filter (Python code, not SQL)."""
    profile = get_profile(session)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No profile yet. Run: python -m app.profile import",
        )
    passed_ids = {job.id for job in filter_jobs([job for job, _ in rows], profile).passed}
    return [row for row in rows if row[0].id in passed_ids]


# Sync "def" (not "async def") on purpose: the SQLModel session is blocking,
# and FastAPI runs sync routes in a thread pool so they don't block each other.
@router.get("", response_model=JobPage)
def list_jobs(
    session: SessionDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobPage:
    statement = build_jobs_query(filters)

    if filters.prefiltered:
        # The pre-filter runs after the SQL query and the page is cut in memory.
        # Fine for a few thousand jobs.
        matching = apply_profile_filter(session, list(session.exec(statement).all()))
        total = len(matching)
        page = matching[offset : offset + limit]  # slicing: like LINQ Skip/Take
    else:
        count_statement = select(func.count()).select_from(statement.subquery())
        total = session.exec(count_statement).one()
        page = list(session.exec(statement.offset(offset).limit(limit)).all())

    analyses = analyses_for(session, [job for job, _ in page])
    return JobPage(
        items=[to_summary(job, application, analyses.get(job.id)) for job, application in page],
        total=total,
        limit=limit,
        offset=offset,
    )


# Declared before "/{job_id}": otherwise "tags" would be taken as a job id
@router.get("/tags", response_model=list[TagCount])
def count_tags(session: SessionDep, filters: FiltersDep) -> list[TagCount]:
    """How many jobs have each stack tag, under the same filters as the list.

    The stack filter itself is ignored here, so every chip keeps its count and
    the user can add a second stack to the selection.
    """
    unfiltered_by_stack = JobFilters(
        filters.source, filters.remote, filters.search, filters.prefiltered, filters.untriaged, []
    )
    rows = list(session.exec(build_jobs_query(unfiltered_by_stack)).all())
    if filters.prefiltered:
        rows = apply_profile_filter(session, rows)
    counts = Counter(tag for job, _ in rows for tag in job.tags)
    return [TagCount(tag=tag, count=count) for tag, count in counts.most_common()]


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, session: SessionDep) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    application = session.exec(select(Application).where(Application.job_id == job_id)).first()
    return to_detail(job, application, session.get(JobAnalysis, job_id))
