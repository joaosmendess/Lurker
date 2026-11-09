"""Collect jobs from every source and save the new ones.

CLI: python -m app.collect
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

import httpx
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.config import get_settings
from app.db import engine, init_db
from app.models import CollectRun, Job, WatchedCompany, utc_now
from app.sources.base import JobSource
from app.sources.github import fetch_github_jobs
from app.sources.greenhouse import fetch_greenhouse_jobs
from app.sources.gupy import fetch_gupy_jobs
from app.sources.lever import fetch_lever_jobs
from app.sources.remotive import fetch_remotive_jobs

logger = logging.getLogger(__name__)

# Sources that don't depend on configuration. Adding one = its module + one line here.
STATIC_SOURCES: dict[str, JobSource] = {
    "remotive": fetch_remotive_jobs,
    "gupy": fetch_gupy_jobs,
}

# Per-company fetchers: they need slug and company_name besides the client.
type CompanyFetcher = Callable[..., list[Job]]
COMPANY_FETCHERS: dict[str, CompanyFetcher] = {
    "greenhouse": fetch_greenhouse_jobs,
    "lever": fetch_lever_jobs,
}

USER_AGENT = "lurker/0.1 (personal job search tool)"


# @dataclass generates __init__, __repr__ and __eq__ from the annotated fields,
# like a C# record or a TS class with only public fields.
@dataclass
class CollectResult:
    fetched: int = 0
    saved: int = 0
    # default_factory again: each result gets its own list (never "= []")
    failed_sources: list[str] = field(default_factory=list)


def github_sources() -> dict[str, JobSource]:
    """One source per configured community repo, e.g. "github:backend-br/vagas"."""
    return {
        f"github:{repo}": partial(fetch_github_jobs, repo=repo)
        for repo in get_settings().github_job_repos
    }


def build_sources(session: Session) -> dict[str, JobSource]:
    """Static sources, the GitHub repos and one source per active watched company.

    Each company/repo is its own source ("greenhouse:gitlab"), so a wrong slug only
    fails that one, and the summary says exactly which.
    """
    sources: dict[str, JobSource] = dict(STATIC_SOURCES)  # copy: never mutate the module dict
    sources.update(github_sources())

    companies = session.exec(select(WatchedCompany).where(col(WatchedCompany.active).is_(True)))
    for company in companies:
        fetcher = COMPANY_FETCHERS.get(company.provider)
        if fetcher is None:
            logger.warning(
                "Unknown provider %r for company %s; skipping", company.provider, company.slug
            )
            continue
        # partial pre-fills slug and company_name, leaving a function that only
        # needs the client: exactly the JobSource contract.
        sources[f"{company.provider}:{company.slug}"] = partial(
            fetcher, slug=company.slug, company_name=company.name
        )
    return sources


def run_sources(client: httpx.Client, sources: dict[str, JobSource]) -> tuple[list[Job], list[str]]:
    """Run every source. A failing source is logged and skipped, never fatal."""
    jobs: list[Job] = []
    failed_sources: list[str] = []
    for name, fetch_jobs in sources.items():
        try:
            source_jobs = fetch_jobs(client)
        except Exception:
            # Broad on purpose: whatever breaks inside a source (network, HTTP,
            # format change, bug), the other sources must still run.
            # logger.exception also logs the full traceback.
            logger.exception("Source %s failed; skipping it", name)
            failed_sources.append(name)
            continue
        logger.info("Source %s: %d jobs", name, len(source_jobs))
        jobs.extend(source_jobs)
    return jobs, failed_sources


def save_new_jobs(session: Session, jobs: list[Job]) -> int:
    """Insert jobs whose id isn't in the database yet. Returns how many were saved.

    Existing jobs are left untouched, so collected_at keeps the first time we saw them.
    """
    # Set comprehension: like a list comprehension, but builds a set (unique values)
    incoming_ids = {job.id for job in jobs}
    existing_ids = set(session.exec(select(Job.id).where(col(Job.id).in_(incoming_ids))).all())

    saved = 0
    for job in jobs:
        if job.id in existing_ids:
            continue
        session.add(job)
        # Also guards against the same id appearing twice in this batch
        existing_ids.add(job.id)
        saved += 1

    session.commit()
    return saved


def collect(session: Session, client: httpx.Client, sources: dict[str, JobSource]) -> CollectResult:
    """Run the sources and save what's new."""
    jobs, failed_sources = run_sources(client, sources)
    saved = save_new_jobs(session, jobs)
    return CollectResult(fetched=len(jobs), saved=saved, failed_sources=failed_sources)


def start_run(db_engine: Engine) -> int:
    """Record that a run started. Uses its own session, separate from the collection's."""
    with Session(db_engine) as session:
        run = CollectRun()
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None
        return run.id


def finish_run(
    db_engine: Engine, run_id: int, result: CollectResult | None, error: str | None
) -> None:
    with Session(db_engine) as session:
        run = session.get(CollectRun, run_id)
        if run is None:
            return
        run.finished_at = utc_now()
        if result is not None:
            run.fetched = result.fetched
            run.saved = result.saved
            run.failed_sources = result.failed_sources
        run.error = error
        session.add(run)
        session.commit()


def latest_run(session: Session) -> CollectRun | None:
    statement = select(CollectRun).order_by(col(CollectRun.started_at).desc()).limit(1)
    return session.exec(statement).first()


def run_collection(db_engine: Engine = engine) -> CollectResult:
    """Full collection with bookkeeping: used by the CLI, the API button and the scheduler.

    The run is recorded in its own sessions so that, even if the collection
    crashes mid-way (and its session is left in a bad state), the CollectRun
    row still gets finished_at and the error.
    """
    run_id = start_run(db_engine)
    try:
        with (
            httpx.Client(headers={"User-Agent": USER_AGENT}) as client,
            Session(db_engine) as session,
        ):
            result = collect(session, client, build_sources(session))
    except Exception as error:
        # Store a short message (never a full traceback with data in it), then re-raise
        finish_run(db_engine, run_id, result=None, error=f"{type(error).__name__}: {error}"[:500])
        raise
    finish_run(db_engine, run_id, result=result, error=None)
    return result


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    init_db()

    result = run_collection()

    logger.info(
        "Done: %d fetched, %d new saved, failed sources: %s",
        result.fetched,
        result.saved,
        result.failed_sources or "none",
    )


# True only when the file is run directly (python -m app.collect), not when imported.
if __name__ == "__main__":
    main()
