"""Watched companies: board links, verification, stats and the terminal commands.

Usage:
    python -m app.companies list
    python -m app.companies add greenhouse gitlab "GitLab"
    python -m app.companies add https://jobs.lever.co/netflix "Netflix"
    python -m app.companies remove greenhouse gitlab
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlmodel import Session, col, select

from app.collect import COMPANY_FETCHERS, USER_AGENT, latest_run, save_new_jobs
from app.db import engine, init_db
from app.filters import filter_jobs
from app.models import Application, Job, WatchedCompany
from app.profile import get_profile
from app.stack import tag_job

# Every host that serves a company's public board, and which provider it belongs to
BOARD_HOSTS: dict[str, str] = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "boards-api.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "api.lever.co": "lever",
}

# Path segments that come right before the slug in the API URLs:
# /v1/boards/{slug}/jobs (Greenhouse) and /v0/postings/{slug} (Lever)
API_PATH_MARKERS = ("boards", "postings")


# Custom exceptions: subclasses of ValueError, so code that catches ValueError
# (the CLI) keeps working, while the API can tell them apart (422 vs 409).
class UnknownProviderError(ValueError):
    pass


class CompanyAlreadyWatchedError(ValueError):
    pass


class BoardNotFoundError(ValueError):
    pass


def parse_board_url(text: str) -> tuple[str, str] | None:
    """Turn a pasted board link into (provider, slug), or None if it isn't one.

    >>> parse_board_url("https://job-boards.greenhouse.io/stone/jobs/123")
    ('greenhouse', 'stone')
    """
    candidate = text.strip()
    if "." not in candidate:
        return None  # a bare slug like "stone", not a link
    if "://" not in candidate:
        candidate = f"https://{candidate}"  # "jobs.lever.co/x" pasted without the scheme

    # urlsplit is like new URL(...) in JS: scheme, hostname, path and query apart
    parts = urlsplit(candidate)
    provider = BOARD_HOSTS.get((parts.hostname or "").lower())
    if provider is None:
        return None

    # Embedded boards: boards.greenhouse.io/embed/job_board?for=stone
    # parse_qs returns lists, because a key may repeat (?for=a&for=b)
    embedded = parse_qs(parts.query).get("for")
    if embedded:
        return provider, embedded[0].lower()

    segments = [segment for segment in parts.path.split("/") if segment]
    for marker in API_PATH_MARKERS:
        if marker in segments:
            index = segments.index(marker)
            if index + 1 < len(segments):
                return provider, segments[index + 1].lower()
    if segments and segments[0] != "embed":
        return provider, segments[0].lower()
    return None


@dataclass(frozen=True)
class AddedCompany:
    company: WatchedCompany
    found_jobs: int  # open jobs on the board right now
    saved_jobs: int  # of those, how many were new to the database


def find_company(session: Session, provider: str, slug: str) -> WatchedCompany | None:
    statement = select(WatchedCompany).where(
        WatchedCompany.provider == provider, WatchedCompany.slug == slug
    )
    return session.exec(statement).first()


def check_new_company(session: Session, provider: str, slug: str) -> None:
    """Raise UnknownProviderError or CompanyAlreadyWatchedError; return None if it's fine."""
    if provider not in COMPANY_FETCHERS:
        supported = ", ".join(COMPANY_FETCHERS)
        raise UnknownProviderError(f"Unknown provider {provider!r}. Supported: {supported}")
    if find_company(session, provider, slug) is not None:
        raise CompanyAlreadyWatchedError(f"{provider}:{slug} is already being watched")


def add_company(session: Session, provider: str, slug: str, name: str) -> WatchedCompany:
    """Add a company without checking its board. Raises like check_new_company."""
    provider = provider.lower().strip()
    slug = slug.lower().strip()
    check_new_company(session, provider, slug)

    company = WatchedCompany(provider=provider, slug=slug, name=name.strip())
    session.add(company)
    session.commit()
    session.refresh(company)  # reload to get the id the database generated
    return company


def add_and_fetch_company(
    session: Session, client: httpx.Client, provider: str, slug: str, name: str
) -> AddedCompany:
    """Fetch the board once and, only if it exists, watch the company and save its jobs.

    So a typo in the slug fails right away, instead of failing silently in
    every collection, and the jobs show up without waiting for the next one.
    Raises BoardNotFoundError (404), httpx.HTTPError (network) or the check_new_company errors.
    """
    provider = provider.lower().strip()
    slug = slug.lower().strip()
    check_new_company(session, provider, slug)  # before the request: no network for a duplicate

    fetch_jobs = COMPANY_FETCHERS[provider]
    try:
        jobs = fetch_jobs(client, slug=slug, company_name=name.strip())
    except httpx.HTTPStatusError as error:
        if error.response.status_code == httpx.codes.NOT_FOUND:
            raise BoardNotFoundError(
                f"No public {provider} board named {slug!r}. Check the link."
            ) from error
        raise

    company = add_company(session, provider, slug, name)
    for job in jobs:
        tag_job(job)
    saved = save_new_jobs(session, jobs)
    return AddedCompany(company=company, found_jobs=len(jobs), saved_jobs=saved)


def company_key(provider: str, slug: str) -> str:
    """The prefix of every job id from this company, and its source name in a collection."""
    return f"{provider}:{slug}"


def key_of_job(job_id: str) -> str:
    # "greenhouse:stone:123" -> "greenhouse:stone". rsplit = split from the right
    return job_id.rsplit(":", 1)[0]


@dataclass(frozen=True)
class CompanyStats:
    job_count: int = 0
    to_triage: int = 0  # untriaged and passing the profile pre-filter
    failed_last_collect: bool = False


def company_stats(session: Session) -> dict[str, CompanyStats]:
    """Stats for every company that has jobs or failed, keyed by company_key."""
    providers = list(COMPANY_FETCHERS)
    # LEFT JOIN: (job, application id or None), so we know what's untriaged
    rows = session.exec(
        select(Job, Application.id)
        .join(Application, col(Application.job_id) == Job.id, isouter=True)
        .where(col(Job.source).in_(providers))
    ).all()

    job_counts = Counter(key_of_job(job.id) for job, _ in rows)
    untriaged = [job for job, application_id in rows if application_id is None]
    profile = get_profile(session)
    passed = filter_jobs(untriaged, profile).passed if profile else untriaged
    triage_counts = Counter(key_of_job(job.id) for job in passed)

    last_run = latest_run(session)
    failed = set(last_run.failed_sources) if last_run else set()

    # "|" on sets is the union: every key that appears in any of the three
    keys = set(job_counts) | set(triage_counts) | failed
    return {
        key: CompanyStats(
            job_count=job_counts[key],  # a Counter returns 0 for a missing key, no KeyError
            to_triage=triage_counts[key],
            failed_last_collect=key in failed,
        )
        for key in keys
    }


def remove_company(session: Session, provider: str, slug: str) -> bool:
    """Delete a company. Returns False if it wasn't being watched."""
    company = find_company(session, provider.lower().strip(), slug.lower().strip())
    if company is None:
        return False
    session.delete(company)
    session.commit()
    return True


def list_companies(session: Session) -> list[WatchedCompany]:
    statement = select(WatchedCompany).order_by(WatchedCompany.provider, WatchedCompany.slug)
    return list(session.exec(statement).all())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.companies")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="show watched companies")

    add = commands.add_parser("add", help="watch a new company (checks its board first)")
    add.add_argument("board", help='"greenhouse", "lever" or a link to the board')
    # nargs="+": one or more values, collected in a list (slug + name, or just name)
    add.add_argument("values", nargs="+", help="slug and name, or only the name after a link")

    remove = commands.add_parser("remove", help="stop watching a company")
    remove.add_argument("provider", choices=sorted(COMPANY_FETCHERS))
    remove.add_argument("slug")

    return parser


def main() -> None:
    args = build_parser().parse_args()
    init_db()

    with Session(engine) as session:
        if args.command == "list":
            companies = list_companies(session)
            if not companies:
                print("No companies watched yet.")
            for company in companies:
                status = "active" if company.active else "inactive"
                print(f"{company.provider:<11} {company.slug:<25} {company.name} ({status})")

        elif args.command == "add":
            parsed = parse_board_url(args.board)
            if parsed is not None and len(args.values) == 1:
                provider, slug = parsed
                name = args.values[0]
            elif parsed is None and len(args.values) == 2:
                provider = args.board
                slug, name = args.values  # unpacking, like const [slug, name] = values
            else:
                raise SystemExit('Use: add <provider> <slug> "Name"  or  add <link> "Name"')

            try:
                with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
                    added = add_and_fetch_company(session, client, provider, slug, name)
            except (ValueError, httpx.HTTPError) as error:
                raise SystemExit(f"Error: {error}") from error
            company = added.company
            print(
                f"Watching {company.provider}:{company.slug} ({company.name}): "
                f"{added.found_jobs} open jobs, {added.saved_jobs} new"
            )

        elif args.command == "remove":
            if not remove_company(session, args.provider, args.slug):
                raise SystemExit(f"{args.provider}:{args.slug} was not being watched")
            print(f"Removed {args.provider}:{args.slug}")


if __name__ == "__main__":
    main()
