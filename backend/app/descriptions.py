"""Re-apply the description cleanup to jobs already in the database.

Run after improving the cleanup rules (new jobs get them automatically):
    python -m app.descriptions
"""

import logging

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Job
from app.sources.base import tidy_lines
from app.sources.gupy import SOURCE_NAME as GUPY
from app.sources.gupy import tidy_gupy_description

logger = logging.getLogger(__name__)


def tidy_description(source: str, text: str) -> str:
    """The same cleanup a source applies when collecting, but on stored plain text."""
    if source == GUPY:
        return tidy_gupy_description(text)
    return tidy_lines(text)


def retidy_all(db_engine: Engine = engine) -> int:
    """Clean every stored description. Returns how many changed."""
    changed = 0
    with Session(db_engine) as session:
        for job in session.exec(select(Job)):
            tidied = tidy_description(job.source, job.description)
            if tidied != job.description:
                job.description = tidied
                session.add(job)
                changed += 1
        session.commit()
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    logger.info("Descriptions updated: %d", retidy_all())


if __name__ == "__main__":
    main()
