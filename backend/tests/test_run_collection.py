import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app import collect as collect_module
from app.collect import latest_run, run_collection
from app.models import CollectRun, Job
from tests.conftest import make_job


def fake_source(client: httpx.Client) -> list[Job]:
    return [make_job("fake:1"), make_job("fake:2")]


def test_successful_run_is_recorded(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a fake source: the real ones would hit the network
    monkeypatch.setattr(collect_module, "STATIC_SOURCES", {"fake": fake_source})

    result = run_collection(engine)

    assert result.saved == 2
    with Session(engine) as session:
        run = latest_run(session)
        assert run is not None
        assert run.finished_at is not None
        assert (run.fetched, run.saved, run.error) == (2, 2, None)
        assert len(session.exec(select(Job)).all()) == 2


def test_crashed_run_records_the_error_and_reraises(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_collect(*args: object) -> None:
        raise RuntimeError("database exploded")

    monkeypatch.setattr(collect_module, "collect", broken_collect)

    with pytest.raises(RuntimeError, match="database exploded"):
        run_collection(engine)

    with Session(engine) as session:
        runs = session.exec(select(CollectRun)).all()
        assert len(runs) == 1
        assert runs[0].finished_at is not None
        assert runs[0].error == "RuntimeError: database exploded"
