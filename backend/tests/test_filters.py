import pytest

from app.filters import filter_jobs, find_excluded_word, normalize, rejection_reason
from app.models import Job, Profile

EXCLUDED = ["estágio", "intern", "staff", "head", "manager", "c++"]


def make_profile(**overrides: object) -> Profile:
    values: dict[str, object] = {
        "resume": "dev",
        "work_modes": ["remote", "hybrid", "onsite"],
        "accepted_cities": ["Maceió"],
        "excluded_title_words": EXCLUDED,
    }
    values.update(overrides)
    return Profile(**values)  # ** unpacks the dict into keyword arguments


def make_job(
    title: str = "Desenvolvedor Pleno", remote: bool | None = True, location: str | None = None
) -> Job:
    return Job(
        id="x:1",
        source="x",
        title=title,
        company="Acme",
        url="https://x",
        remote=remote,
        location=location,
    )


def test_normalize_removes_accents_and_case() -> None:
    assert normalize("Estágio em MACEIÓ") == "estagio em maceio"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Estágio em Desenvolvimento", "estágio"),
        ("ESTAGIO - TI", "estágio"),  # no accent, upper case
        ("Software Engineering Intern", "intern"),
        ("Staff Engineer", "staff"),
        ("Head of Engineering", "head"),
        ("Engineering Manager", "manager"),
        ("Desenvolvedor C++", "c++"),  # symbols are escaped in the regex
        ("Internal Tools Engineer", None),  # "intern" only as a whole word
        ("Headless CMS Developer", None),
        ("Staffing Systems Developer", None),
        ("Desenvolvedor Full Stack Pleno", None),
    ],
)
def test_find_excluded_word(title: str, expected: str | None) -> None:
    assert find_excluded_word(title, EXCLUDED) == expected


@pytest.mark.parametrize(
    ("remote", "location", "work_modes", "should_pass"),
    [
        (True, "Worldwide", ["remote"], True),
        (True, None, ["hybrid", "onsite"], False),  # remote not accepted
        (False, "Maceió - Alagoas", ["remote", "hybrid"], True),
        (False, "MACEIO, AL", ["onsite"], True),  # accents/case don't matter
        (False, "São Paulo - São Paulo", ["remote", "hybrid", "onsite"], False),
        (False, None, ["hybrid"], False),  # in-person job with no location
        (False, "Maceió", ["remote"], False),  # in-person not accepted at all
        (None, "São Paulo", ["remote"], True),  # unknown: the AI decides
    ],
)
def test_work_mode_rules(
    remote: bool | None, location: str | None, work_modes: list[str], should_pass: bool
) -> None:
    profile = make_profile(work_modes=work_modes)
    job = make_job(remote=remote, location=location)

    assert (rejection_reason(job, profile) is None) is should_pass


@pytest.mark.parametrize(
    ("location", "strict", "should_pass"),
    [
        ("São Paulo, Sao Paulo, Brasil", False, True),  # default: the AI decides
        ("São Paulo, Sao Paulo, Brasil", True, False),
        ("Maceió - AL", True, True),  # accepted city
        ("Brasil", True, True),  # a country is not a city
        ("LATAM", True, True),
        ("Remoto - Brasil", True, True),
        (None, True, True),  # no location: nothing to judge
    ],
)
def test_strict_unknown_work_mode(location: str | None, strict: bool, should_pass: bool) -> None:
    profile = make_profile(strict_unknown_work_mode=strict)
    job = make_job(remote=None, location=location)

    assert (rejection_reason(job, profile) is None) is should_pass


def test_title_is_checked_before_work_mode() -> None:
    reason = rejection_reason(
        make_job(title="Staff Engineer", remote=False, location="Recife"), make_profile()
    )

    assert reason == "title contains 'staff'"


def test_rejection_reason_mentions_the_location() -> None:
    reason = rejection_reason(make_job(remote=False, location="Recife - PE"), make_profile())

    assert reason == "hybrid/onsite outside accepted cities (Recife - PE)"


def test_filter_jobs_splits_passed_and_rejected() -> None:
    good = make_job(title="Dev Pleno")
    bad = make_job(title="Estágio TI")

    result = filter_jobs([good, bad], make_profile())

    assert result.passed == [good]
    assert result.rejected == [(bad, "title contains 'estágio'")]
