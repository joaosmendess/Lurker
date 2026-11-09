"""Manage watched companies from the terminal (until the API exists in phase 3).

Usage:
    python -m app.companies list
    python -m app.companies add greenhouse gitlab "GitLab"
    python -m app.companies remove greenhouse gitlab
"""

import argparse

from sqlmodel import Session, select

from app.collect import COMPANY_FETCHERS
from app.db import engine, init_db
from app.models import WatchedCompany


# Custom exceptions: subclasses of ValueError, so code that catches ValueError
# (the CLI) keeps working, while the API can tell them apart (422 vs 409).
class UnknownProviderError(ValueError):
    pass


class CompanyAlreadyWatchedError(ValueError):
    pass


def find_company(session: Session, provider: str, slug: str) -> WatchedCompany | None:
    statement = select(WatchedCompany).where(
        WatchedCompany.provider == provider, WatchedCompany.slug == slug
    )
    return session.exec(statement).first()


def add_company(session: Session, provider: str, slug: str, name: str) -> WatchedCompany:
    """Add a company. Raises UnknownProviderError or CompanyAlreadyWatchedError."""
    provider = provider.lower().strip()
    slug = slug.lower().strip()
    if provider not in COMPANY_FETCHERS:
        supported = ", ".join(COMPANY_FETCHERS)
        raise UnknownProviderError(f"Unknown provider {provider!r}. Supported: {supported}")
    if find_company(session, provider, slug) is not None:
        raise CompanyAlreadyWatchedError(f"{provider}:{slug} is already being watched")

    company = WatchedCompany(provider=provider, slug=slug, name=name.strip())
    session.add(company)
    session.commit()
    session.refresh(company)  # reload to get the id the database generated
    return company


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

    add = commands.add_parser("add", help="watch a new company")
    add.add_argument("provider", choices=sorted(COMPANY_FETCHERS))
    add.add_argument("slug", help='board name in the URL, e.g. "gitlab"')
    add.add_argument("name", help="company display name")

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
            try:
                company = add_company(session, args.provider, args.slug, args.name)
            except ValueError as error:
                raise SystemExit(f"Error: {error}") from error
            print(f"Watching {company.provider}:{company.slug} ({company.name})")

        elif args.command == "remove":
            if not remove_company(session, args.provider, args.slug):
                raise SystemExit(f"{args.provider}:{args.slug} was not being watched")
            print(f"Removed {args.provider}:{args.slug}")


if __name__ == "__main__":
    main()
