"""Gupy source: Brazilian job portal.

NOT an official API: this is the endpoint the public portal (portal.gupy.io) calls.
It may change without notice, so the response is validated strictly and requests
are spaced out. We only read public listings; applying is always done by hand.
"""

import logging
import re
import time
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.config import get_settings
from app.models import Job
from app.sources.base import REQUEST_TIMEOUT_SECONDS, as_utc, html_to_text, tidy_lines

SOURCE_NAME = "gupy"
GUPY_URL = "https://portal.gupy.io/api/job-search/jobs"
PAGE_SIZE = 100
MAX_PAGES_PER_TERM = 5
DELAY_BETWEEN_REQUESTS_SECONDS = 1.0

# Gupy's workplaceType -> Job.remote. Unknown values map to None ("unknown").
REMOTE_BY_WORKPLACE_TYPE: dict[str, bool] = {
    "remote": True,
    "hybrid": False,
    "on-site": False,
}

logger = logging.getLogger(__name__)


class GupyJob(BaseModel):
    """Shape of one item in Gupy's "data" array (only the fields we use)."""

    # Gupy uses camelCase (careerPageName); this maps it to snake_case attributes
    model_config = ConfigDict(alias_generator=to_camel)

    id: int
    name: str
    career_page_name: str
    job_url: str
    description: str = ""
    workplace_type: str | None = None
    city: str | None = None
    state: str | None = None
    published_date: datetime | None = None


def fetch_gupy_jobs(client: httpx.Client, search_terms: list[str] | None = None) -> list[Job]:
    """Fetch jobs for every search term, without duplicates.

    Raises on network/HTTP/format errors. search_terms defaults to the
    GUPY_SEARCH_TERMS setting; tests pass it explicitly.
    """
    terms = search_terms if search_terms is not None else get_settings().gupy_search_terms

    # dict keeps insertion order, so the result follows the order jobs were found
    jobs_by_id: dict[str, Job] = {}
    for term in terms:
        for raw_job in fetch_term(client, term):
            job = parse_job(raw_job)
            if job is not None and job.id not in jobs_by_id:
                jobs_by_id[job.id] = job

    logger.info("Gupy returned %d unique jobs for %d terms", len(jobs_by_id), len(terms))
    return list(jobs_by_id.values())


def fetch_term(client: httpx.Client, term: str) -> list[dict[str, Any]]:
    """Fetch every page for one search term (until a page comes back incomplete)."""
    raw_jobs: list[dict[str, Any]] = []
    for page in range(MAX_PAGES_PER_TERM):
        page_jobs = fetch_page(client, term, offset=page * PAGE_SIZE)
        raw_jobs.extend(page_jobs)
        # pagination.total just repeats the limit, so a short page is the only end signal
        if len(page_jobs) < PAGE_SIZE:
            break
    return raw_jobs


def fetch_page(client: httpx.Client, term: str, offset: int) -> list[dict[str, Any]]:
    """Fetch one page. Waits a bit first to be gentle with an unofficial endpoint."""
    time.sleep(DELAY_BETWEEN_REQUESTS_SECONDS)
    response = client.get(
        GUPY_URL,
        params={"jobName": term, "offset": offset, "limit": PAGE_SIZE},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload: dict[str, Any] = response.json()
    if not isinstance(payload.get("data"), list):
        raise ValueError("Gupy response has no 'data' list; the format may have changed")
    return payload["data"]


def parse_job(raw_job: dict[str, Any]) -> Job | None:
    """Validate and map one item. Returns None (and logs) if the item is invalid."""
    try:
        gupy_job = GupyJob.model_validate(raw_job)
    except ValidationError as error:
        logger.warning("Skipping invalid Gupy job id=%s: %s", raw_job.get("id"), error)
        return None
    return to_job(gupy_job)


def to_job(gupy_job: GupyJob) -> Job:
    """Map a Gupy item to our normalized Job."""
    return Job(
        id=f"{SOURCE_NAME}:{gupy_job.id}",
        source=SOURCE_NAME,
        title=gupy_job.name.strip(),
        company=gupy_job.career_page_name.strip(),
        url=gupy_job.job_url,
        location=build_location(gupy_job.city, gupy_job.state),
        remote=REMOTE_BY_WORKPLACE_TYPE.get(gupy_job.workplace_type or ""),
        # Gupy already sends plain text; cleaning anyway guards against HTML showing up
        description=tidy_gupy_description(html_to_text(gupy_job.description)),
        published_at=as_utc(gupy_job.published_date),
    )


# Gupy's standard section titles. Its API glues them to the text around them:
# "...gente.Responsabilidades e atribuiçõesDesenvolver APIs.Atuar com..."
SECTION_HEADINGS: tuple[str, ...] = (
    "Responsabilidades e atribuições",
    "Requisitos e qualificações",
    "Informações adicionais",
)
# In these sections every line is one item, so they become "- " lists
LIST_SECTIONS: frozenset[str] = frozenset(SECTION_HEADINGS[:2])

# A sentence end glued to the next one: "segurança.Definir", "global.Ao se".
# The next word must be Capitalized with 2+ lowercase letters, or a short
# Portuguese word ("Ao", "Os", "É"...). That leaves tech names like "Vue.Js",
# "Node.JS" or "ASP.NET" alone.
SHORT_WORDS = "Ao|Aos|As|Os|Em|No|Na|Nos|Nas|Se|Um|Uma|É|O|A|E"
GLUED_SENTENCE = re.compile(
    rf"(?<=[a-zà-ÿ0-9)])([.!?;])(?=[A-ZÀ-Ý][a-zà-ÿ]{{2,}}|(?:{SHORT_WORDS})\b)"
)
# A ";" glued to the next item, common in benefit lists: "refeição;👨‍🎓 Desconto"
GLUED_SEMICOLON = re.compile(r";(?=\S)")


def tidy_gupy_description(text: str) -> str:
    """Restore the structure Gupy's API flattens: headings, sentences and list items.

    Idempotent, so it can be re-applied to descriptions already in the database.
    """
    for heading in SECTION_HEADINGS:
        # Put each section title on its own line (keeping the previous sentence's period)
        text = re.sub(rf"\s*{re.escape(heading)}:?\s*", f"\n{heading}\n", text)
    text = GLUED_SENTENCE.sub(r"\1\n", text)
    text = GLUED_SEMICOLON.sub(";\n", text)
    text = tidy_lines(text)

    lines: list[str] = []
    in_list_section = False
    for line in text.splitlines():
        if line in SECTION_HEADINGS:
            in_list_section = line in LIST_SECTIONS
        elif in_list_section and not line.startswith("- "):
            line = f"- {line}"
        lines.append(line)
    return "\n".join(lines)


def build_location(city: str | None, state: str | None) -> str | None:
    """'Jundiaí' + 'São Paulo' -> 'Jundiaí - São Paulo'; both empty -> None."""
    parts = [part.strip() for part in (city, state) if part and part.strip()]
    return " - ".join(parts) or None
