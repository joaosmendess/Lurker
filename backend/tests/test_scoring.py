import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.llm import LLMBadAnswerError, LLMConfig
from app.main import app
from app.models import Application, JobAnalysis, Profile
from app.routers.resume import require_llm_config
from app.scoring import parse_score, pending_jobs, progress, score_pending
from tests.conftest import make_job
from tests.test_resume import ORIGINAL

CONFIG = LLMConfig("https://llm.test/v1", "test-key", "fake-model")


def score_json(score: int = 80, pitch: str = "Desenvolvedor focado em .NET.") -> str:
    return json.dumps(
        {
            "score": score,
            "summary": "Bom encaixe.",
            "matches": [".NET", " "],
            "gaps": ["Kubernetes"],
            "red_flags": [],
            "pitch": pitch,
        }
    )


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def fake_client(replies: list[httpx.Response]) -> httpx.Client:
    pending = list(replies)

    def answer(request: httpx.Request) -> httpx.Response:
        return pending.pop(0)

    return httpx.Client(transport=httpx.MockTransport(answer))


@pytest.fixture
def seeded(engine: Engine) -> Engine:
    with Session(engine) as session:
        session.add(
            Profile(id=1, resume=ORIGINAL, work_modes=["remote"], preferred_stack=["React"])
        )
        session.add_all(
            [
                make_job("gupy:1", "Dev .NET"),
                make_job("gupy:2", "Dev React", tags=["React"]),
                make_job("gupy:3", "Dev Java"),
                make_job("gupy:4", "Dev presencial", remote=False, location="Recife"),
            ]
        )
        session.add(Application(job_id="gupy:3", status="discarded"))
        session.commit()
    return engine


# --- Parsing ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [score_json(), f"Aqui está:\n```json\n{score_json()}\n```", f"  {score_json()}  "],
)
def test_parse_score_finds_the_json(text: str) -> None:
    assert parse_score(text).score == 80


@pytest.mark.parametrize("text", ["sem json", '{"score": 150, "summary": "x"}', '{"score": 70}'])
def test_parse_score_rejects_bad_answers(text: str) -> None:
    with pytest.raises(LLMBadAnswerError):
        parse_score(text)


# --- Which jobs ---------------------------------------------------------------------


def test_pending_skips_triaged_filtered_and_puts_preferred_stack_first(seeded: Engine) -> None:
    with Session(seeded) as session:
        profile = session.get(Profile, 1)
        assert profile is not None
        ids = [job.id for job in pending_jobs(session, profile)]

    # gupy:3 is triaged, gupy:4 is on-site outside accepted cities; React goes first
    assert ids == ["gupy:2", "gupy:1"]


# --- Batch --------------------------------------------------------------------------


def run(engine: Engine, replies: list[httpx.Response], sleeps: list[float] | None = None) -> Any:
    waited = sleeps if sleeps is not None else []
    sleep: Callable[[float], None] = waited.append
    return score_pending(engine, limit=10, config=CONFIG, client=fake_client(replies), sleep=sleep)


def test_batch_scores_and_saves_with_pitch_check(seeded: Engine) -> None:
    invented = "Tenho 5 anos com Kubernetes."
    result = run(seeded, [reply(score_json(90, pitch=invented)), reply(score_json(60))])

    assert (result.analyzed, result.failed, result.stopped_reason) == (2, 0, None)
    with Session(seeded) as session:
        react = session.get(JobAnalysis, "gupy:2")
        dotnet = session.get(JobAnalysis, "gupy:1")
        assert react is not None and dotnet is not None
        assert (react.score, dotnet.score) == (90, 60)
        assert react.matches == [".NET"]  # blank items dropped
        assert len(react.pitch_warnings) == 2  # the "5" and "Kubernetes"
        assert dotnet.pitch_warnings == []


def test_rate_limit_waits_what_the_provider_asks(seeded: Engine) -> None:
    waited: list[float] = []
    limited = httpx.Response(429, headers={"retry-after": "7"})

    result = run(seeded, [limited, reply(score_json()), reply(score_json())], waited)

    assert waited == [7.0]
    assert result.analyzed == 2


def test_daily_quota_gone_stops_the_batch(seeded: Engine) -> None:
    result = run(seeded, [httpx.Response(429, headers={"retry-after": "3600"})])

    assert result.analyzed == 0
    assert result.stopped_reason is not None
    assert progress.stopped_reason == result.stopped_reason


def test_bad_job_is_skipped_and_the_batch_goes_on(seeded: Engine) -> None:
    result = run(seeded, [reply("lixo"), reply("lixo"), reply(score_json())])

    assert (result.analyzed, result.failed) == (1, 1)


# --- API ----------------------------------------------------------------------------


def test_job_list_is_sorted_by_score_and_detail_has_the_analysis(
    seeded: Engine, client: TestClient
) -> None:
    run(seeded, [reply(score_json(40)), reply(score_json(95))])  # gupy:2 = 40, gupy:1 = 95

    items = client.get("/jobs").json()["items"]
    detail = client.get("/jobs/gupy:1").json()

    assert [item["id"] for item in items][:2] == ["gupy:1", "gupy:2"]
    assert items[0]["score"] == 95
    assert items[-1]["score"] is None  # not analyzed: last
    assert detail["analysis"]["gaps"] == ["Kubernetes"]


def test_status_counts_analyzed_and_pending(seeded: Engine, client: TestClient) -> None:
    # The first job gets a score; the second gets two bad answers and stays pending
    run(seeded, [reply(score_json()), reply("lixo"), reply("lixo")])

    body = client.get("/scoring").json()

    assert (body["analyzed"], body["pending"]) == (1, 1)
    assert body["running"] is False


def test_start_without_ai_configured_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.llm import LLMNotConfiguredError

    def not_configured() -> LLMConfig:
        raise LLMNotConfiguredError("Set LLM_API_KEY and LLM_MODEL in backend/.env")

    monkeypatch.setattr("app.routers.resume.get_llm_config", not_configured)

    assert client.post("/scoring").status_code == 503


def test_start_without_resume_is_409(client: TestClient) -> None:
    app.dependency_overrides[require_llm_config] = lambda: CONFIG

    assert client.post("/scoring").status_code == 409
