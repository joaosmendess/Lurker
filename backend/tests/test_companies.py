from collections.abc import Iterator

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.companies import add_company, list_companies, parse_board_url, remove_company
from app.db import build_engine, init_db
from app.models import WatchedCompany


@pytest.fixture
def session() -> Iterator[Session]:
    engine = build_engine("sqlite://")
    init_db(engine)
    with Session(engine) as db_session:
        yield db_session


def test_add_normalizes_and_assigns_id(session: Session) -> None:
    company = add_company(session, " Greenhouse ", " GitLab ", " GitLab ")

    assert company.id is not None
    assert (company.provider, company.slug, company.name) == ("greenhouse", "gitlab", "GitLab")
    assert company.active is True


def test_add_rejects_unknown_provider(session: Session) -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        add_company(session, "workday", "acme", "Acme")


def test_add_rejects_duplicates(session: Session) -> None:
    add_company(session, "lever", "acme", "Acme")

    with pytest.raises(ValueError, match="already being watched"):
        add_company(session, "lever", "ACME", "Acme again")


def test_same_slug_is_allowed_on_different_providers(session: Session) -> None:
    add_company(session, "lever", "acme", "Acme")
    add_company(session, "greenhouse", "acme", "Acme")

    assert len(list_companies(session)) == 2


def test_database_enforces_unique_provider_and_slug(session: Session) -> None:
    # Bypasses add_company's check to prove the UNIQUE constraint itself works
    session.add(WatchedCompany(provider="lever", slug="acme", name="A"))
    session.add(WatchedCompany(provider="lever", slug="acme", name="B"))

    with pytest.raises(IntegrityError):
        session.commit()


def test_remove(session: Session) -> None:
    add_company(session, "lever", "acme", "Acme")

    assert remove_company(session, "lever", "acme") is True
    assert remove_company(session, "lever", "acme") is False
    assert list_companies(session) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://job-boards.greenhouse.io/Stone/jobs/123", ("greenhouse", "stone")),
        ("boards.greenhouse.io/embed/job_board?for=vtex", ("greenhouse", "vtex")),
        ("https://boards-api.greenhouse.io/v1/boards/ebanx/jobs", ("greenhouse", "ebanx")),
        ("https://jobs.lever.co/netflix", ("lever", "netflix")),
        ("https://api.lever.co/v0/postings/netflix?mode=json", ("lever", "netflix")),
        ("stone", None),  # a bare slug, not a link
        ("https://example.com/stone", None),  # not a board site
        ("https://boards.greenhouse.io/embed/job_board", None),  # embed without ?for=
        ("https://jobs.lever.co/", None),  # no slug at all
    ],
)
def test_parse_board_url(text: str, expected: tuple[str, str] | None) -> None:
    assert parse_board_url(text) == expected
