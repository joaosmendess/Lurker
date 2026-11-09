import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db import build_engine, init_db
from app.models import Job
from app.stack import detect_stack, merge_tags, retag_all
from tests.conftest import make_job


@pytest.mark.parametrize(
    ("text_in", "expected"),
    [
        ("Desenvolvedor .NET Core com C# e SQL Server", ["C#", ".NET", "SQL Server"]),
        ("ASP.NET MVC", [".NET"]),
        ("Java e Spring Boot", ["Java", "Spring"]),
        ("JavaScript e TypeScript", ["JavaScript", "TypeScript"]),  # not Java
        ("Node.js, NestJS", ["Node.js", "NestJS"]),  # the "js" doesn't make JavaScript
        ("React Native e Expo", ["React Native"]),  # not React
        ("React e React Native", ["React", "React Native"]),
        ("Vue.js 3", ["Vue"]),
        ("Golang ou Go", ["Go"]),
        ("Goiânia - GO, let's go", []),  # neither the state nor the English word
        ("C++ e Rust", ["Rust", "C++"]),
        ("PostgreSQL, Postgres e MongoDB", ["PostgreSQL", "MongoDB"]),
        ("AWS (Lambda, S3) e Docker/K8s", ["AWS", "Docker", "Kubernetes"]),
        ("Analista Protheus (ADVPL)", ["Protheus/ADVPL"]),
        ("escala de trabalho 6x1", []),  # "scala" inside a word
        ("site example.net", []),  # a domain is not .NET
    ],
)
def test_detect_stack(text_in: str, expected: list[str]) -> None:
    assert detect_stack(text_in) == expected


def test_detect_stack_combines_texts() -> None:
    assert detect_stack("Dev Backend", "Experiência com Python") == ["Python"]


def test_merge_tags_keeps_display_order_and_unknown_last() -> None:
    assert merge_tags(["Docker", "Custom"], ["Python", "Docker"]) == ["Python", "Docker", "Custom"]


def test_retag_all(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(make_job("gupy:1", title="Dev React", description="Node.js no backend"))
        session.add(make_job("gupy:2", title="Analista", description="Sem tecnologia"))
        session.commit()

    assert retag_all(engine) == 1
    with Session(engine) as session:
        job = session.get(Job, "gupy:1")
        assert job is not None
        assert job.tags == ["Node.js", "React"]
    assert retag_all(engine) == 0  # idempotent


def test_init_db_adds_tags_column_to_an_old_job_table() -> None:
    engine = build_engine("sqlite://")
    with engine.begin() as connection:
        # The job table as it was before the tags column existed
        connection.execute(text("CREATE TABLE job (id VARCHAR PRIMARY KEY, title VARCHAR)"))
        connection.execute(text("INSERT INTO job (id, title) VALUES ('old:1', 'Dev')"))

    init_db(engine)
    init_db(engine)  # running again must not fail

    assert "tags" in {column["name"] for column in inspect(engine).get_columns("job")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT tags FROM job")).scalar() == "[]"


# --- API ------------------------------------------------------------------------


@pytest.fixture
def seed(engine: Engine) -> None:
    """Only for the API tests below (requested with usefixtures), not the whole module."""
    with Session(engine) as session:
        session.add(make_job("gupy:1", title="Dev React", tags=["React", "Node.js"]))
        session.add(make_job("gupy:2", title="Dev Mobile", tags=["React Native"]))
        session.add(make_job("gupy:3", title="Dev .NET", tags=[".NET", "C#"]))
        session.commit()


@pytest.mark.usefixtures("seed")
def test_list_filters_by_any_of_the_stacks(client: TestClient) -> None:
    body = client.get("/jobs", params=[("stack", "React"), ("stack", ".NET")]).json()

    # "React" must not match "React Native" (gupy:2)
    assert sorted(item["id"] for item in body["items"]) == ["gupy:1", "gupy:3"]
    assert body["items"][0]["tags"]


@pytest.mark.usefixtures("seed")
def test_stack_filter_treats_like_wildcards_literally(client: TestClient) -> None:
    assert client.get("/jobs", params={"stack": "%"}).json()["total"] == 0


@pytest.mark.usefixtures("seed")
def test_tag_counts_ignore_the_stack_filter(client: TestClient) -> None:
    counts = client.get("/jobs/tags", params={"stack": "React"}).json()

    assert {item["tag"]: item["count"] for item in counts} == {
        "React": 1,
        "Node.js": 1,
        "React Native": 1,
        ".NET": 1,
        "C#": 1,
    }
