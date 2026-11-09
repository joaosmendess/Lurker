from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlmodel import Session, select

from app.db import build_engine, init_db
from app.models import Profile
from app.profile import (
    ProfileData,
    describe,
    get_profile,
    load_profile_file,
    save_profile,
)

EXAMPLE_PATH = Path(__file__).parent.parent / "profile.example.toml"


@pytest.fixture
def session() -> Iterator[Session]:
    engine = build_engine("sqlite://")
    init_db(engine)
    with Session(engine) as db_session:
        yield db_session


def make_data(**overrides: object) -> ProfileData:
    """**overrides collects keyword args into a dict, like C# params + named args."""
    values: dict[str, object] = {
        "resume": "Full-stack dev with C# and React.",
        "work_modes": ["remote", "hybrid"],
        "accepted_cities": ["Maceió"],
        "seniority_levels": [" Junior ", "PLENO"],
        "contract_types": ["clt", "pj"],
        "salary_expectation": "CLT: R$ 5.000",
        "excluded_title_words": ["Estágio", " Staff ", ""],
    }
    values.update(overrides)
    return ProfileData.model_validate(values)


def test_example_file_is_valid() -> None:
    data = load_profile_file(EXAMPLE_PATH)

    assert data.work_modes == ["remote"]


def test_load_profile_file_reads_toml(tmp_path: Path) -> None:
    # tmp_path is a built-in fixture: a fresh temporary folder per test
    profile_file = tmp_path / "profile.toml"
    profile_file.write_text(
        'resume = """\nDev C#\n"""\nwork_modes = ["onsite"]\naccepted_cities = ["Maceió"]\n',
        encoding="utf-8",
    )

    data = load_profile_file(profile_file)

    assert data.resume == "Dev C#"
    assert data.accepted_cities == ["Maceió"]


def test_words_and_seniority_are_normalized() -> None:
    data = make_data()

    assert data.seniority_levels == ["junior", "pleno"]
    assert data.excluded_title_words == ["estágio", "staff"]


def test_invalid_work_mode_is_rejected() -> None:
    with pytest.raises(ValidationError, match="work_modes"):
        make_data(work_modes=["remoto"])


def test_empty_resume_is_rejected() -> None:
    with pytest.raises(ValidationError, match="resume must not be empty"):
        make_data(resume="   ")


def test_save_creates_then_overwrites_the_single_profile(session: Session) -> None:
    save_profile(session, make_data())
    save_profile(session, make_data(accepted_cities=["Recife"], work_modes=["remote"]))

    profiles = session.exec(select(Profile)).all()
    assert len(profiles) == 1

    profile = get_profile(session)
    assert profile is not None
    assert profile.accepted_cities == ["Recife"]  # JSON list round-trips as a list
    assert profile.work_modes == ["remote"]


def test_describe_never_prints_the_resume(session: Session) -> None:
    profile = save_profile(session, make_data(resume="SECRET resume text"))

    summary = describe(profile)

    assert "SECRET" not in summary
    assert "18 chars" in summary
