"""Collect jobs from every source and save the new ones.

CLI: python -m app.collect
"""

import logging
from dataclasses import dataclass, field

import httpx
from sqlmodel import Session, col, select

from app.db import engine, init_db
from app.models import Job
from app.sources.base import JobSource
from app.sources.gupy import fetch_gupy_jobs
from app.sources.remotive import fetch_remotive_jobs

logger = logging.getLogger(__name__)

# Registry of sources. Adding a source = writing its module + one line here.
SOURCES: dict[str, JobSource] = {
    "remotive": fetch_remotive_jobs,
    "gupy": fetch_gupy_jobs,
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


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    init_db()

    with (
        httpx.Client(headers={"User-Agent": USER_AGENT}) as client,
        Session(engine) as session,
    ):
        result = collect(session, client, SOURCES)

    logger.info(
        "Done: %d fetched, %d new saved, failed sources: %s",
        result.fetched,
        result.saved,
        result.failed_sources or "none",
    )


# True only when the file is run directly (python -m app.collect), not when imported.
if __name__ == "__main__":
    main()
