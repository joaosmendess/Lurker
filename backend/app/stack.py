"""Detect the technologies a job mentions, as display tags ("React", ".NET").

Tags are a VIEW filter only (CLAUDE.md): no job is discarded because of them.

Backfill the jobs already in the database:
    python -m app.stack
"""

import logging
import re

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Job

logger = logging.getLogger(__name__)

# Tag -> pattern. Order here is the display order. Patterns are matched
# case-insensitively unless compiled with their own flags below.
# (?<![\w.]) / (?![\w]) = whole word, also rejecting a leading "." so that the
# "js" inside "Node.js" or the "net" inside "ASP.NET" never count on their own.
_W = r"(?<![\w.#+])"  # left boundary
_E = r"(?![\w#+])"  # right boundary

STACK_PATTERNS: dict[str, str] = {
    "C#": rf"{_W}c#{_E}|{_W}csharp{_E}",
    ".NET": rf"(?<![\w])\.net(?:\s*core)?{_E}|{_W}dotnet{_E}|asp\.net",
    "Java": rf"{_W}java{_E}(?!\s*script)",
    "Kotlin": rf"{_W}kotlin{_E}",
    "Spring": rf"{_W}spring(?:\s*boot)?{_E}",
    "Python": rf"{_W}python{_E}",
    "Django": rf"{_W}django{_E}",
    "FastAPI": rf"{_W}fastapi{_E}",
    "JavaScript": rf"{_W}javascript{_E}|{_W}ecmascript{_E}",
    "TypeScript": rf"{_W}typescript{_E}",
    "Node.js": rf"{_W}node(?:\.?js)?{_E}",
    "NestJS": rf"{_W}nest\.?js{_E}",
    "React": rf"{_W}react(?:\.?js)?{_E}(?![\s-]*native)",
    "React Native": rf"{_W}react[\s-]*native{_E}",
    "Next.js": rf"{_W}next\.?js{_E}",
    "Angular": rf"{_W}angular(?:\.?js)?{_E}",
    "Vue": rf"{_W}vue(?:\.?js)?{_E}",
    "PHP": rf"{_W}php{_E}",
    "Laravel": rf"{_W}laravel{_E}",
    "Ruby": rf"{_W}ruby{_E}(?!\s*on\s*rails)",
    "Rails": rf"{_W}rails{_E}",
    "Go": rf"{_W}golang{_E}",  # plain "Go" is matched separately (case-sensitive)
    "Rust": rf"{_W}rust{_E}",
    "C++": rf"{_W}c\+\+",
    "Swift": rf"{_W}swift{_E}",
    "Flutter": rf"{_W}flutter{_E}",
    "Android": rf"{_W}android{_E}",
    "iOS": rf"{_W}ios{_E}",
    "Elixir": rf"{_W}elixir{_E}",
    "Scala": rf"{_W}scala{_E}",
    "Delphi": rf"{_W}delphi{_E}",
    "Protheus/ADVPL": rf"{_W}protheus{_E}|{_W}advpl{_E}",
    "SAP/ABAP": rf"{_W}abap{_E}|{_W}sap\s+(?:abap|hana|s/4)",
    "SQL Server": rf"{_W}sql\s*server{_E}|{_W}mssql{_E}|{_W}t-sql{_E}",
    "PostgreSQL": rf"{_W}postgre(?:s|sql)?{_E}",
    "MySQL": rf"{_W}mysql{_E}",
    "MongoDB": rf"{_W}mongo(?:db)?{_E}",
    "Redis": rf"{_W}redis{_E}",
    "AWS": rf"{_W}aws{_E}|amazon web services",
    "Azure": rf"{_W}azure{_E}",
    "GCP": rf"{_W}gcp{_E}|google cloud",
    "Docker": rf"{_W}docker{_E}",
    "Kubernetes": rf"{_W}kubernetes{_E}|{_W}k8s{_E}",
    "Terraform": rf"{_W}terraform{_E}",
    "Kafka": rf"{_W}kafka{_E}",
    "RabbitMQ": rf"{_W}rabbitmq{_E}",
    "GraphQL": rf"{_W}graphql{_E}",
}

_COMPILED: dict[str, re.Pattern[str]] = {
    tag: re.compile(pattern, re.IGNORECASE) for tag, pattern in STACK_PATTERNS.items()
}
# "Go" only when written exactly so (capital G, standalone): "go" is a common
# English word and "GO" a Brazilian state (Goiânia - GO).
_GO_EXACT = re.compile(r"(?<![\w.-])Go(?![\w-])")
_TAG_ORDER = {tag: index for index, tag in enumerate(STACK_PATTERNS)}


def detect_stack(*texts: str) -> list[str]:
    """Tags found in any of the texts, in display order, without duplicates.

    *texts collects any number of positional arguments into a tuple, like
    C#'s "params string[] texts".
    """
    combined = "\n".join(texts)
    found = {tag for tag, pattern in _COMPILED.items() if pattern.search(combined)}
    if "Go" not in found and _GO_EXACT.search(combined):
        found.add("Go")
    return sorted(found, key=_TAG_ORDER.__getitem__)


def merge_tags(*tag_lists: list[str]) -> list[str]:
    """Union of tag lists in display order (unknown tags, e.g. from labels, go last)."""
    merged = {tag for tags in tag_lists for tag in tags}
    return sorted(merged, key=lambda tag: (_TAG_ORDER.get(tag, len(_TAG_ORDER)), tag))


def tag_job(job: Job) -> None:
    """Add detected tags to the job, keeping the ones a source already set (e.g. labels)."""
    job.tags = merge_tags(job.tags, detect_stack(job.title, job.description))


def retag_all(db_engine: Engine = engine) -> int:
    """Recompute tags for every stored job. Returns how many changed."""
    changed = 0
    with Session(db_engine) as session:
        for job in session.exec(select(Job)):
            before = list(job.tags)
            tag_job(job)
            if job.tags != before:
                session.add(job)
                changed += 1
        session.commit()
    return changed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    logger.info("Jobs with updated tags: %d", retag_all())


if __name__ == "__main__":
    main()
