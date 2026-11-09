from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from app.collect import github_sources
from app.sources.github import (
    company_from_title,
    fetch_github_jobs,
    location_from_tag,
    markdown_to_text,
    split_title_tag,
)

ISSUES_URL = "https://api.github.com/repos/backend-br/vagas/issues"
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)

BODY = """### Sobre a empresa

A **Acme** faz software. Veja [o site](https://acme.example).

<!-- template comment -->
### Requisitos

* Python e user_id_value
- Docker
"""


def make_issue(number: int, title: str, created_at: str, **fields: Any) -> dict[str, Any]:
    issue: dict[str, Any] = {
        "number": number,
        "title": title,
        "html_url": f"https://github.com/backend-br/vagas/issues/{number}",
        "created_at": created_at,
        "body": BODY,
        "labels": [{"name": "Remoto"}, {"name": "Python"}],
    }
    issue.update(fields)
    return issue


@respx.mock
def test_maps_recent_issues_and_skips_old_ones_and_pull_requests() -> None:
    issues = [
        make_issue(1, "[Remoto] Desenvolvedor(a) Backend Pleno - Acme", "2026-11-08T10:00:00Z"),
        make_issue(
            2,
            "[Joinville/SC] Back-end Developer (Node.js)",
            "2026-11-01T10:00:00Z",
            labels=[{"name": "Presencial"}],
        ),
        make_issue(3, "[Remoto] Vaga antiga - Velha", "2026-06-01T10:00:00Z"),  # > 90 days
        make_issue(4, "Bump deps", "2026-11-08T10:00:00Z", pull_request={"url": "x"}),
        {"number": 5, "html_url": "x"},  # invalid: no title
    ]
    route = respx.get(ISSUES_URL).mock(return_value=httpx.Response(200, json=issues))

    with httpx.Client() as client:
        jobs = fetch_github_jobs(client, repo="backend-br/vagas", now=NOW)

    assert route.calls.last.request.url.params["state"] == "open"
    assert [job.id for job in jobs] == ["github:backend-br:1", "github:backend-br:2"]
    remote_job, onsite_job = jobs

    assert remote_job.source == "github"
    assert remote_job.title == "Desenvolvedor(a) Backend Pleno - Acme"
    assert remote_job.company == "Acme"
    assert remote_job.url == "https://github.com/backend-br/vagas/issues/1"
    assert remote_job.remote is True
    assert remote_job.location is None
    assert remote_job.published_at == datetime(2026, 11, 8, 10, 0, tzinfo=UTC)

    assert onsite_job.company == "Comunidade backend-br"  # no company in the title
    assert onsite_job.location == "Joinville/SC"
    assert onsite_job.remote is False


@respx.mock
def test_paginates_until_a_short_page() -> None:
    full_page = [make_issue(n, f"Dev {n} - Acme", "2026-11-08T10:00:00Z") for n in range(100)]

    def respond(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        return httpx.Response(200, json=full_page if page == "1" else [])

    route = respx.get(ISSUES_URL).mock(side_effect=respond)

    with httpx.Client() as client:
        jobs = fetch_github_jobs(client, repo="backend-br/vagas", now=NOW)

    assert route.call_count == 2
    assert len(jobs) == 100


@respx.mock
def test_raises_on_http_error() -> None:
    respx.get(ISSUES_URL).mock(return_value=httpx.Response(403, json={"message": "rate limit"}))

    with httpx.Client() as client, pytest.raises(httpx.HTTPStatusError):
        fetch_github_jobs(client, repo="backend-br/vagas", now=NOW)


@respx.mock
def test_raises_when_format_changes() -> None:
    respx.get(ISSUES_URL).mock(return_value=httpx.Response(200, json={"items": []}))

    with httpx.Client() as client, pytest.raises(ValueError, match="not a list"):
        fetch_github_jobs(client, repo="backend-br/vagas", now=NOW)


def test_markdown_to_text() -> None:
    assert markdown_to_text(BODY) == "\n".join(
        [
            "Sobre a empresa:",  # "###" heading -> line ending in ":" (the UI's heading signal)
            "A Acme faz software. Veja o site (https://acme.example).",
            "Requisitos:",
            "- Python e user_id_value",  # single "_" is not treated as italics
            "- Docker",
        ]
    )


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("[Remoto] Dev - Acme", ("Remoto", "Dev - Acme")),
        (
            "  [Híbrido / São Paulo, Brasil] Engenheiro",
            ("Híbrido / São Paulo, Brasil", "Engenheiro"),
        ),
        ("Sem tag nenhuma", (None, "Sem tag nenhuma")),
    ],
)
def test_split_title_tag(title: str, expected: tuple[str | None, str]) -> None:
    assert split_title_tag(title) == expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("Desenvolvedor(a) Backend Pleno - White Label e Plataforma - Mimix AI", "Mimix AI"),
        ("Engenheiro de Software Backend Sênior na Coodesh", "Coodesh"),
        ("Full Stack Sênior — AI & Agents na WeatherWise | 4 dias / 32h", "WeatherWise"),
        ("Back-end ou Full Stack Developer (Node.js + React)", None),
    ],
)
def test_company_from_title(role: str, expected: str | None) -> None:
    assert company_from_title(role) == expected


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("Remoto", None),
        ("Híbrido / São Paulo, Brasil", "São Paulo, Brasil"),
        ("Joinville/SC", "Joinville/SC"),  # "/" without spaces is part of the place
        (None, None),
    ],
)
def test_location_from_tag(tag: str | None, expected: str | None) -> None:
    assert location_from_tag(tag) == expected


def test_github_sources_reads_repos_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_JOB_REPOS", "backend-br/vagas, frontendbr/vagas")
    from app.config import get_settings

    get_settings.cache_clear()  # lru_cache would keep the settings from another test
    try:
        assert list(github_sources()) == ["github:backend-br/vagas", "github:frontendbr/vagas"]
    finally:
        get_settings.cache_clear()
