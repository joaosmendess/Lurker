from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import Settings
from app.llm import LLMConfig, LLMNotConfiguredError
from app.main import app
from app.routers.resume import require_llm_config
from tests.conftest import make_job
from tests.test_resume import ORIGINAL

type FakeWeb = dict[str, httpx.Response]

JOB_ID = "gupy:1"
CHAT_PATH = "/v1/chat/completions"


@pytest.fixture(autouse=True)
def setup(engine: Engine, client: TestClient) -> Iterator[None]:
    with Session(engine) as session:
        session.add(make_job(JOB_ID, "Dev .NET Pleno"))
        session.commit()
    # A fake provider: requests go to llm.test, which only fake_web answers
    app.dependency_overrides[require_llm_config] = lambda: LLMConfig(
        "https://llm.test/v1", "test-key", "fake-model"
    )
    yield  # the client fixture clears every override afterwards


def save_resume(client: TestClient) -> None:
    response = client.put("/profile", json={"resume": ORIGINAL, "work_modes": ["remote"]})
    assert response.status_code == 200, response.text


def model_answers(fake_web: FakeWeb, resume: str) -> None:
    content = (
        f"===CURRICULO===\n{resume}\n===AJUSTES===\n- Resumo focado em .NET\n"
        "===FALTANDO===\n- Kubernetes"
    )
    fake_web[CHAT_PATH] = httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_generate_saves_and_get_returns_it(client: TestClient, fake_web: FakeWeb) -> None:
    save_resume(client)
    model_answers(fake_web, ORIGINAL)

    created = client.post(f"/jobs/{JOB_ID}/resume")

    assert created.status_code == 200, created.text
    body = created.json()
    assert body["content"] == ORIGINAL.strip()
    assert body["changes"] == ["Resumo focado em .NET"]
    assert body["missing"] == ["Kubernetes"]
    assert body["warnings"] == []
    assert body["model"] == "fake-model"
    assert client.get(f"/jobs/{JOB_ID}/resume").json() == body


def test_changed_experience_comes_back_as_warning(client: TestClient, fake_web: FakeWeb) -> None:
    save_resume(client)
    model_answers(fake_web, ORIGINAL.replace("03/2022", "03/2019"))

    warnings = client.post(f"/jobs/{JOB_ID}/resume").json()["warnings"]

    assert len(warnings) == 2  # the changed line + the invented year


def test_regenerating_replaces_the_previous_version(client: TestClient, fake_web: FakeWeb) -> None:
    save_resume(client)
    model_answers(fake_web, ORIGINAL)
    client.post(f"/jobs/{JOB_ID}/resume")
    model_answers(fake_web, ORIGINAL + "\nIdiomas: inglês")

    client.post(f"/jobs/{JOB_ID}/resume")

    assert client.get(f"/jobs/{JOB_ID}/resume").json()["content"].endswith("Idiomas: inglês")


def test_get_before_generating_is_404(client: TestClient) -> None:
    assert client.get(f"/jobs/{JOB_ID}/resume").status_code == 404


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.post("/jobs/gupy:999/resume").status_code == 404


def test_without_resume_is_409_and_does_not_call_the_ai(client: TestClient) -> None:
    # fake_web is empty: any call to the AI would fail the test
    assert client.post(f"/jobs/{JOB_ID}/resume").status_code == 409


def test_quota_used_up_is_429(client: TestClient, fake_web: FakeWeb) -> None:
    save_resume(client)
    fake_web[CHAT_PATH] = httpx.Response(429)

    assert client.post(f"/jobs/{JOB_ID}/resume").status_code == 429


def test_provider_error_is_502(client: TestClient, fake_web: FakeWeb) -> None:
    save_resume(client)
    fake_web[CHAT_PATH] = httpx.Response(400, json={"error": {"message": "model not found"}})

    response = client.post(f"/jobs/{JOB_ID}/resume")

    assert response.status_code == 502
    assert "model not found" in response.json()["detail"]


def test_not_configured_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides.pop(require_llm_config)

    def not_configured() -> LLMConfig:
        raise LLMNotConfiguredError("Set LLM_API_KEY and LLM_MODEL in backend/.env")

    monkeypatch.setattr("app.routers.resume.get_llm_config", not_configured)

    response = client.post(f"/jobs/{JOB_ID}/resume")

    assert response.status_code == 503
    assert "LLM_API_KEY" in response.json()["detail"]


def test_status_never_returns_the_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # _env_file=None: build Settings from these values only, ignoring the real .env
    settings = Settings(_env_file=None, llm_api_key="gsk_secret", llm_model="some-model")  # type: ignore[call-arg]
    monkeypatch.setattr("app.routers.resume.get_settings", lambda: settings)

    response = client.get("/llm/status")

    assert response.json()["configured"] is True
    assert response.json()["model"] == "some-model"
    assert "gsk_secret" not in response.text
