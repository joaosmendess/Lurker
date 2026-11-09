import json
from typing import Any

import httpx
import pytest

from app.llm import LLMBadAnswerError, LLMConfig, LLMError, LLMRateLimitedError
from app.resume import ask_model, check_preserved, parse_answer, plain_text

ORIGINAL = """\
JOÃO TESTE
Maceió – AL

RESUMO
Desenvolvedor focado em .NET.

EXPERIÊNCIA PROFISSIONAL
ACME LTDA
Desenvolvedor Full Stack | 03/2022 – Atual
• Criei APIs em ASP.NET Core.

FORMAÇÃO
Sistemas de Informação | 2018 – 2022
"""

CONFIG = LLMConfig(base_url="https://llm.test/v1", api_key="test-key", model="fake-model")


def test_reformatted_but_faithful_resume_has_no_warnings() -> None:
    # Bullet swapped for "- ", extra spaces, a new summary: all allowed by the rules
    tailored = ORIGINAL.replace("• Criei", "- Criei").replace(
        "Desenvolvedor focado em .NET.", "Desenvolvedor .NET e ASP.NET Core."
    )
    tailored = tailored.replace("03/2022 – Atual", "03/2022   –   Atual")

    assert check_preserved(ORIGINAL, tailored) == []


def test_changed_date_line_is_reported() -> None:
    tailored = ORIGINAL.replace("03/2022 – Atual", "01/2020 – Atual")

    warnings = check_preserved(ORIGINAL, tailored)

    assert any("Desenvolvedor Full Stack | 03/2022 – Atual" in item for item in warnings)
    assert any("2020" in item and "não está" in item for item in warnings)


def test_removed_experience_line_is_reported() -> None:
    tailored = ORIGINAL.replace("Sistemas de Informação | 2018 – 2022\n", "")

    assert len(check_preserved(ORIGINAL, tailored)) == 1


def test_invented_year_is_reported_once() -> None:
    tailored = ORIGINAL + "\nconcluído em 2019\noutra coisa de 2019\n"

    warnings = check_preserved(ORIGINAL, tailored)

    assert warnings == ["Apareceu um número que não está no seu currículo: 2019"]


@pytest.mark.parametrize("invented", ["Experiência com .NET 8.", "Mais de 5 anos de experiência."])
def test_invented_number_in_summary_is_reported(invented: str) -> None:
    tailored = ORIGINAL.replace("Desenvolvedor focado em .NET.", invented)

    assert len(check_preserved(ORIGINAL, tailored)) == 1


WITH_SKILLS = (
    ORIGINAL
    + """
HABILIDADES
Backend: .NET Core, Node.js
Cloud & DevOps: AWS, Docker
Dados & ORM: Entity Framework, Prisma
Frontend & Mobile: React Native
"""
)


def test_invented_terms_from_the_job_are_reported() -> None:
    # The real case: "Cloud" and "Native" both exist in the resume, but not together
    summary = (
        "Atua em projetos Cloud Native na AWS e colabora com Tech Leads, Product Managers e QA."
    )
    tailored = WITH_SKILLS.replace("Desenvolvedor focado em .NET.", summary)

    warnings = check_preserved(WITH_SKILLS, tailored)

    assert warnings == [
        "Termos que não estão no seu currículo: Cloud Native, Tech Leads, Product Managers, QA"
    ]


def test_lowercase_hyphenated_invention_is_reported() -> None:
    tailored = WITH_SKILLS.replace("Desenvolvedor focado em .NET.", "Cria soluções cloud-native.")

    assert check_preserved(WITH_SKILLS, tailored) == [
        "Termos que não estão no seu currículo: cloud-native"
    ]


def test_slash_joined_known_terms_are_fine() -> None:
    # "AWS" and "Docker" are both in the resume; joined by "/" they're not a new term
    tailored = WITH_SKILLS.replace("Desenvolvedor focado em .NET.", "Atua com AWS/Docker.")

    assert check_preserved(WITH_SKILLS, tailored) == []


def test_lookalike_characters_become_plain() -> None:
    assert plain_text("Full‑Stack com 3 anos") == "Full-Stack com 3 anos"


def test_rewritten_summary_with_known_terms_is_fine() -> None:
    summary = "Desenvolvedor com Node.js e AWS. Atua com Docker e React Native em APIs."
    tailored = WITH_SKILLS.replace("Desenvolvedor focado em .NET.", summary)

    assert check_preserved(WITH_SKILLS, tailored) == []


def test_removed_skill_is_reported() -> None:
    tailored = WITH_SKILLS.replace("Dados & ORM: Entity Framework, Prisma\n", "")

    assert check_preserved(WITH_SKILLS, tailored) == [
        "Habilidades que sumiram: Entity Framework, Prisma"
    ]


def test_reordered_skills_are_fine() -> None:
    tailored = WITH_SKILLS.replace(
        "Backend: .NET Core, Node.js\nCloud & DevOps: AWS, Docker",
        "Cloud & DevOps: Docker, AWS\nBackend: Node.js, .NET Core",
    )

    assert check_preserved(WITH_SKILLS, tailored) == []


def test_repeated_line_is_reported() -> None:
    # An experience line written twice (only known words, so this is the only warning)
    tailored = ORIGINAL + "- Criei APIs em ASP.NET Core.\n"

    assert check_preserved(ORIGINAL, tailored) == [
        "Linha repetida no currículo ajustado: “criei apis em asp.net core.”"
    ]


def answer_text(resume: str = ORIGINAL, changes: str = "- Resumo reescrito") -> str:
    return f"===CURRICULO===\n{resume}\n===AJUSTES===\n{changes}\n===FALTANDO===\n- Kubernetes\n"


def test_parse_answer_splits_the_three_sections() -> None:
    answer = parse_answer(answer_text(changes="- Resumo reescrito\n• Habilidades reordenadas"))

    assert answer.resume == ORIGINAL.strip()
    assert answer.changes == ["Resumo reescrito", "Habilidades reordenadas"]
    assert answer.missing == ["Kubernetes"]


def test_parse_answer_tolerates_accent_spacing_and_empty_lists() -> None:
    text = f"== CURRÍCULO ==\n{ORIGINAL}\n=== AJUSTES ===\nNenhum\n===FALTANDO===\n"

    answer = parse_answer(text)

    assert answer.resume.startswith("JOÃO TESTE")
    assert (answer.changes, answer.missing) == ([], [])


@pytest.mark.parametrize("text", ["Aqui está o currículo: ...", "===AJUSTES===\n- algo"])
def test_parse_answer_without_resume_section_is_a_bad_answer(text: str) -> None:
    with pytest.raises(LLMBadAnswerError):
        parse_answer(text)


def chat_reply(content: str, finish_reason: str = "stop") -> httpx.Response:
    choice = {"message": {"content": content}, "finish_reason": finish_reason}
    return httpx.Response(200, json={"choices": [choice]})


def fake_client(replies: list[httpx.Response]) -> tuple[httpx.Client, list[dict[str, Any]]]:
    """A client that answers the replies in order and records each request body."""
    sent: list[dict[str, Any]] = []

    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return replies[len(sent) - 1]

    return httpx.Client(transport=httpx.MockTransport(answer)), sent


def test_ask_model_retries_once_after_a_bad_answer() -> None:
    client, sent = fake_client([chat_reply("no markers here"), chat_reply(answer_text())])

    answer = ask_model(client, CONFIG, "prompt")

    assert answer.changes == ["Resumo reescrito"]
    assert len(sent) == 2
    assert sent[0]["model"] == "fake-model"
    assert sent[0]["max_tokens"] >= 4096  # room for reasoning + a whole resume


def test_answer_cut_by_the_output_limit_is_retried() -> None:
    cut = chat_reply(answer_text()[:40], finish_reason="length")
    client, sent = fake_client([cut, chat_reply(answer_text())])

    assert ask_model(client, CONFIG, "prompt").resume == ORIGINAL.strip()
    assert len(sent) == 2


def test_ask_model_gives_up_after_two_bad_answers() -> None:
    client, sent = fake_client([chat_reply("===CURRICULO===\ncurto")] * 2)

    with pytest.raises(LLMError, match="expected format"):
        ask_model(client, CONFIG, "prompt")
    assert len(sent) == 2


def test_rate_limit_is_not_retried() -> None:
    client, sent = fake_client([httpx.Response(429)])

    with pytest.raises(LLMRateLimitedError):
        ask_model(client, CONFIG, "prompt")
    assert len(sent) == 1
