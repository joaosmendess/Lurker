from collections.abc import Iterator

import httpx
import pytest
from sqlmodel import Session, select

from app import collect as collect_module
from app.collect import STATIC_SOURCES, build_sources, collect, save_new_jobs
from app.db import build_engine, init_db
from app.models import Job, WatchedCompany
from app.sources.base import JobSource


def make_job(job_id: str, title: str = "Dev") -> Job:
    return Job(id=job_id, source=job_id.split(":")[0], title=title, company="Acme", url="https://x")


# A fixture that uses yield: code before it is setup, code after it is teardown
# (like a test class constructor + Dispose in xUnit).
@pytest.fixture
def session() -> Iterator[Session]:
    engine = build_engine("sqlite://")
    init_db(engine)
    with Session(engine) as db_session:
        yield db_session


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    # Fake sources below never use it, so nothing reaches the network
    with httpx.Client() as http_client:
        yield http_client


def failing_source(client: httpx.Client) -> list[Job]:
    raise httpx.ConnectError("source is down")


def all_jobs(session: Session) -> list[Job]:
    return list(session.exec(select(Job).order_by(Job.id)).all())


def test_failing_source_does_not_stop_the_others(session: Session, client: httpx.Client) -> None:
    sources: dict[str, JobSource] = {
        "broken": failing_source,
        "ok": lambda _client: [make_job("ok:1"), make_job("ok:2")],
    }

    result = collect(session, client, sources)

    assert result.failed_sources == ["broken"]
    assert result.fetched == 2
    assert result.saved == 2
    assert [job.id for job in all_jobs(session)] == ["ok:1", "ok:2"]


def test_running_twice_does_not_duplicate(session: Session, client: httpx.Client) -> None:
    sources: dict[str, JobSource] = {"ok": lambda _client: [make_job("ok:1"), make_job("ok:2")]}

    first = collect(session, client, sources)
    second = collect(session, client, sources)

    assert first.saved == 2
    assert second.saved == 0
    assert second.fetched == 2
    assert len(all_jobs(session)) == 2


def test_existing_jobs_are_not_overwritten(session: Session) -> None:
    save_new_jobs(session, [make_job("ok:1", title="Original")])

    saved = save_new_jobs(session, [make_job("ok:1", title="Changed"), make_job("ok:2")])

    assert saved == 1
    stored = session.get(Job, "ok:1")
    assert stored is not None
    assert stored.title == "Original"


def test_build_sources_adds_one_source_per_active_company(
    session: Session, client: httpx.Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetcher(client: httpx.Client, *, slug: str, company_name: str) -> list[Job]:
        calls.append((slug, company_name))
        return []

    monkeypatch.setattr(collect_module, "COMPANY_FETCHERS", {"greenhouse": fake_fetcher})
    session.add(WatchedCompany(provider="greenhouse", slug="acme", name="Acme"))
    session.add(WatchedCompany(provider="greenhouse", slug="globex", name="Globex"))
    session.add(WatchedCompany(provider="greenhouse", slug="paused", name="Paused", active=False))
    session.add(WatchedCompany(provider="workday", slug="unknown", name="Unknown provider"))
    session.commit()

    sources = build_sources(session)

    company_sources = [name for name in sources if name not in STATIC_SOURCES]
    assert company_sources == ["greenhouse:acme", "greenhouse:globex"]
    assert set(STATIC_SOURCES) <= set(sources)  # "<=" on sets means "is subset of"

    # Each source carries its own slug (the classic loop-closure bug would repeat "globex")
    sources["greenhouse:acme"](client)
    sources["greenhouse:globex"](client)
    assert calls == [("acme", "Acme"), ("globex", "Globex")]


def test_build_sources_does_not_mutate_static_sources(session: Session) -> None:
    session.add(WatchedCompany(provider="lever", slug="acme", name="Acme"))
    session.commit()

    build_sources(session)

    assert "lever:acme" not in STATIC_SOURCES


def test_same_id_twice_in_one_batch_is_saved_once(session: Session) -> None:
    saved = save_new_jobs(session, [make_job("ok:1"), make_job("ok:1")])

    assert saved == 1
    assert len(all_jobs(session)) == 1
