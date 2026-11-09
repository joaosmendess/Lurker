"""Job routes: list (with filters and pagination) and detail."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, func, or_, select
from sqlmodel.sql.expression import Select

from app.db import get_session
from app.filters import filter_jobs
from app.models import Application, Job
from app.profile import get_profile
from app.schemas import JobDetail, JobPage, to_detail, to_summary

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Annotated + Depends: FastAPI calls get_session() for each request and passes
# the result in. Same idea as constructor injection with a scoped DbContext in ASP.NET.
SessionDep = Annotated[Session, Depends(get_session)]

# Each result row is a (job, its application or None) tuple
type JobRow = tuple[Job, Application | None]


def build_jobs_query(
    source: str | None, remote: bool | None, search: str | None, untriaged: bool
) -> Select[JobRow]:
    """SELECT jobs + their application (LEFT JOIN) with the optional filters, newest first."""
    # outerjoin = LEFT JOIN: jobs without an application come back with None
    statement = select(Job, Application).outerjoin(
        Application, col(Application.job_id) == col(Job.id)
    )
    if source is not None:
        statement = statement.where(Job.source == source)
    if remote is not None:
        statement = statement.where(Job.remote == remote)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(col(Job.title).ilike(pattern), col(Job.company).ilike(pattern))
        )
    if untriaged:
        statement = statement.where(col(Application.id).is_(None))
    # Jobs without a publish date go last; id breaks ties so pages are stable
    return statement.order_by(
        col(Job.published_at).desc().nulls_last(),
        col(Job.collected_at).desc(),
        col(Job.id),
    )


# Sync "def" (not "async def") on purpose: the SQLModel session is blocking,
# and FastAPI runs sync routes in a thread pool so they don't block each other.
@router.get("", response_model=JobPage)
def list_jobs(
    session: SessionDep,
    source: str | None = None,
    remote: bool | None = None,
    q: Annotated[str | None, Query(max_length=100, description="search in title/company")] = None,
    prefiltered: Annotated[
        bool, Query(description="only jobs that pass the profile pre-filter")
    ] = False,
    untriaged: Annotated[
        bool, Query(description="only jobs without an application (not triaged yet)")
    ] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobPage:
    statement = build_jobs_query(source, remote, q, untriaged)

    if prefiltered:
        profile = get_profile(session)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No profile yet. Run: python -m app.profile import",
            )
        # The pre-filter is Python code, so it runs after the SQL query and the
        # page is cut in memory. Fine for a few thousand jobs.
        rows: list[JobRow] = list(session.exec(statement).all())
        passed_ids = {job.id for job in filter_jobs([job for job, _ in rows], profile).passed}
        matching = [row for row in rows if row[0].id in passed_ids]
        total = len(matching)
        page = matching[offset : offset + limit]  # slicing: like LINQ Skip/Take
    else:
        count_statement = select(func.count()).select_from(statement.subquery())
        total = session.exec(count_statement).one()
        page = list(session.exec(statement.offset(offset).limit(limit)).all())

    return JobPage(
        items=[to_summary(job, application) for job, application in page],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, session: SessionDep) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    application = session.exec(select(Application).where(Application.job_id == job_id)).first()
    return to_detail(job, application)
