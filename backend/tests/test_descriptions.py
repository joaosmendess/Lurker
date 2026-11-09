import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.descriptions import retidy_all
from app.models import Job
from app.sources.base import tidy_lines
from app.sources.gupy import tidy_gupy_description
from tests.conftest import make_job

# Shape of a real Gupy description (shortened): headings and items glued together
GUPY_RAW = (
    "Somos uma empresa de tecnologia.Ao se juntar, você cresce.Junte-se a nós!\n"
    "Responsabilidades e atribuiçõesDesenvolver aplicações Android.Integrar com APIs RESTful.\n"
    "Requisitos e qualificaçõesExperiência com Kotlin; • Conhecimento em Vue.Js e ASP.NET\n"
    "Informações adicionais🍛 Vale-refeição;📚 Auxílio educação;Trabalho remoto."
)

GUPY_EXPECTED = "\n".join(
    [
        "Somos uma empresa de tecnologia.",
        "Ao se juntar, você cresce.",  # short Portuguese word after the period
        "Junte-se a nós!",
        "Responsabilidades e atribuições",
        "- Desenvolver aplicações Android.",
        "- Integrar com APIs RESTful.",
        "Requisitos e qualificações",
        "- Experiência com Kotlin;",
        "- Conhecimento em Vue.Js e ASP.NET",  # tech names are not split
        "Informações adicionais",
        "🍛 Vale-refeição;",  # not a list section: plain lines, split at glued ";"
        "📚 Auxílio educação;",
        "Trabalho remoto.",
    ]
)


def test_tidy_gupy_restores_structure() -> None:
    assert tidy_gupy_description(GUPY_RAW) == GUPY_EXPECTED


def test_tidy_gupy_is_idempotent() -> None:
    once = tidy_gupy_description(GUPY_RAW)

    assert tidy_gupy_description(once) == once


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Stack: • Python • SQL", "Stack:\n- Python\n- SQL"),
        ("· Helpdesk – HaloPSA\n· RMM – Intune", "- Helpdesk – HaloPSA\n- RMM – Intune"),
        ("a\n\n\n  b  \n•\n", "a\nb"),  # blank lines and lone bullets dropped
        ("Node.js e C# • 3 anos", "Node.js e C#\n- 3 anos"),
    ],
)
def test_tidy_lines(text: str, expected: str) -> None:
    assert tidy_lines(text) == expected


def test_retidy_all_updates_stored_descriptions(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(make_job("gupy:1", description=GUPY_RAW))
        session.add(make_job("greenhouse:acme:1", description="- ok\n- already clean"))
        session.commit()

    changed = retidy_all(engine)

    assert changed == 1  # only the Gupy one needed work
    with Session(engine) as session:
        gupy_job = session.get(Job, "gupy:1")
        assert gupy_job is not None
        assert gupy_job.description == GUPY_EXPECTED
    assert retidy_all(engine) == 0  # second run: nothing left to change
