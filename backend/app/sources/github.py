"""GitHub source: Brazilian community job repositories (backend-br/vagas and similar).

Each job is an open issue: the title follows "[Place or mode] Role - Company",
labels carry mode/seniority/stack, and the body is Markdown with "###" sections.
Uses the official GitHub REST API (no login needed for this volume).
"""

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.models import Job
from app.sources.base import REQUEST_TIMEOUT_SECONDS, as_utc, tidy_lines

SOURCE_NAME = "github"
ISSUES_URL = "https://api.github.com/repos/{repo}/issues"
PER_PAGE = 100
MAX_PAGES = 3
# Many repos never close old issues; a job opened months ago is almost surely gone
MAX_AGE_DAYS = 90

REMOTE_LABELS = {"remoto", "remote"}
IN_PERSON_LABELS = {"híbrido", "hibrido", "presencial", "hybrid", "on-site", "onsite"}

logger = logging.getLogger(__name__)


class GitHubLabel(BaseModel):
    name: str


class GitHubIssue(BaseModel):
    """One issue from the issues endpoint (only the fields we use)."""

    number: int
    title: str
    html_url: str
    created_at: datetime
    body: str | None = None
    labels: list[GitHubLabel] = Field(default_factory=list)
    # Present only on pull requests, which the issues endpoint also returns
    pull_request: dict[str, Any] | None = None


def fetch_github_jobs(client: httpx.Client, *, repo: str, now: datetime | None = None) -> list[Job]:
    """Fetch recent open issues of one repo ("owner/name"). Raises on network/HTTP errors."""
    now = now or datetime.now(UTC)
    oldest_allowed = now - timedelta(days=MAX_AGE_DAYS)

    jobs: list[Job] = []
    for page in range(1, MAX_PAGES + 1):
        raw_issues = fetch_page(client, repo, page)
        for raw_issue in raw_issues:
            job = parse_issue(raw_issue, repo=repo, oldest_allowed=oldest_allowed)
            if job is not None:
                jobs.append(job)
        if len(raw_issues) < PER_PAGE:
            break

    logger.info("GitHub %s returned %d recent jobs", repo, len(jobs))
    return jobs


def fetch_page(client: httpx.Client, repo: str, page: int) -> list[dict[str, Any]]:
    response = client.get(
        ISSUES_URL.format(repo=repo),
        params={"state": "open", "per_page": PER_PAGE, "page": page},
        headers={"Accept": "application/vnd.github+json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload: Any = response.json()
    if not isinstance(payload, list):
        raise ValueError("GitHub issues response is not a list; the format may have changed")
    return payload


def parse_issue(raw_issue: dict[str, Any], *, repo: str, oldest_allowed: datetime) -> Job | None:
    """Validate and map one issue. None for invalid items, pull requests and old issues."""
    try:
        issue = GitHubIssue.model_validate(raw_issue)
    except ValidationError as error:
        logger.warning(
            "Skipping invalid GitHub issue %s#%s: %s", repo, raw_issue.get("number"), error
        )
        return None
    if issue.pull_request is not None:
        return None
    published_at = as_utc(issue.created_at)
    if published_at is None or published_at < oldest_allowed:
        return None
    return to_job(issue, repo=repo, published_at=published_at)


def to_job(issue: GitHubIssue, *, repo: str, published_at: datetime) -> Job:
    owner = repo.split("/")[0]
    tag, role = split_title_tag(issue.title)
    labels = {label.name.strip().lower() for label in issue.labels}
    return Job(
        id=f"{SOURCE_NAME}:{owner}:{issue.number}",
        source=SOURCE_NAME,
        title=role,
        company=company_from_title(role) or f"Comunidade {owner}",
        url=issue.html_url,
        location=location_from_tag(tag),
        remote=remote_from_labels(labels, tag),
        description=markdown_to_text(issue.body or ""),
        published_at=published_at,
    )


TITLE_TAG = re.compile(r"^\s*\[([^\]]+)\]\s*")


def split_title_tag(title: str) -> tuple[str | None, str]:
    """Split the leading tag: "[Remoto] Dev - Acme" -> ("Remoto", "Dev - Acme")."""
    match = TITLE_TAG.match(title)
    if match is None:
        return None, title.strip()
    return match.group(1).strip(), title[match.end() :].strip()


# "... - Acme" or "... na Acme", optionally followed by " | extra info".
# The greedy "^.*" makes the match start at the LAST separator, so in
# "Full Stack — AI & Agents na WeatherWise" the company is "WeatherWise".
COMPANY_SUFFIX = re.compile(r"^.*(?:\s[-–—]\s|\sna\s)([^|]{2,40}?)\s*(?:\|.*)?$")


def company_from_title(role: str) -> str | None:
    match = COMPANY_SUFFIX.search(role)
    return match.group(1).strip() if match else None


MODE_WORDS = {"remoto", "remote", "híbrido", "hibrido", "presencial", "hybrid"}


def location_from_tag(tag: str | None) -> str | None:
    """The [tag] is a place unless it's only a work mode ("[Remoto]", "[Híbrido]")."""
    if tag is None:
        return None
    if tag.lower() in MODE_WORDS:
        return None
    # "[Híbrido / São Paulo, Brasil]" -> keep the place part. Only " / " with spaces
    # separates; "Joinville/SC" is a single place.
    parts = [
        part.strip() for part in re.split(r"\s+/\s+", tag) if part.strip().lower() not in MODE_WORDS
    ]
    return " / ".join(parts) or None


def remote_from_labels(labels: set[str], tag: str | None) -> bool | None:
    tag_words = {word.strip().lower() for word in re.split(r"[/,]", tag or "")}
    if labels & REMOTE_LABELS or tag_words & REMOTE_LABELS:
        return True
    if labels & IN_PERSON_LABELS or tag_words & IN_PERSON_LABELS:
        return False
    return None


MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$", re.MULTILINE)
MARKDOWN_BULLET = re.compile(r"^\s*[*+]\s+", re.MULTILINE)
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
# Single "_" is left out on purpose: it would eat the underscores of identifiers
# like user_id_value
MARKDOWN_EMPHASIS = re.compile(r"(\*\*|__|\*)(?=\S)(.+?)(?<=\S)\1")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def markdown_to_text(markdown: str) -> str:
    """Markdown body -> the plain-text structure the UI renders (headings, "- " items)."""
    text = HTML_COMMENT.sub("", markdown)  # issue templates leave hidden comments
    # "### Requisitos" -> "Requisitos:" (a trailing colon is the UI's heading signal)
    text = MARKDOWN_HEADING.sub(lambda match: f"{match.group(1).rstrip(':')}:", text)
    text = MARKDOWN_BULLET.sub("- ", text)
    text = MARKDOWN_LINK.sub(r"\1 (\2)", text)
    text = MARKDOWN_EMPHASIS.sub(r"\2", text)
    return tidy_lines(text)
