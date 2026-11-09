"""Load my profile (resume + preferences) from a local TOML file into the database.

Usage:
    python -m app.profile import            # reads backend/profile.toml
    python -m app.profile import other.toml
    python -m app.profile show

profile.toml holds personal data and is git-ignored; see profile.example.toml.
"""

import argparse
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator
from sqlmodel import Session

from app.config import BACKEND_DIR
from app.db import engine, init_db
from app.models import PROFILE_ID, Profile, utc_now

DEFAULT_PROFILE_PATH: Path = BACKEND_DIR / "profile.toml"

# Literal restricts a str to these exact values, like a TS union "remote" | "hybrid"
type WorkMode = Literal["remote", "hybrid", "onsite"]
type ContractType = Literal["clt", "pj"]


class ProfileData(BaseModel):
    """Validated content of profile.toml. A typo like "remoto" fails with a clear error."""

    resume: str
    work_modes: list[WorkMode]
    accepted_cities: list[str] = []  # safe in Pydantic: defaults are copied per instance
    seniority_levels: list[str] = []
    contract_types: list[ContractType] = []
    salary_expectation: str = ""
    excluded_title_words: list[str] = []

    @field_validator("resume")
    @classmethod
    def resume_not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("resume must not be empty")
        return value.strip()

    @field_validator("seniority_levels", "excluded_title_words")
    @classmethod
    def lowercase_items(cls, values: list[str]) -> list[str]:
        """Matching is case-insensitive, so store these lowercased and trimmed."""
        return [value.strip().lower() for value in values if value.strip()]


def load_profile_file(path: Path) -> ProfileData:
    """Read and validate a TOML profile file."""
    # tomllib requires binary mode: TOML is always UTF-8, so it decodes by itself
    with path.open("rb") as file:
        raw = tomllib.load(file)
    return ProfileData.model_validate(raw)


def get_profile(session: Session) -> Profile | None:
    return session.get(Profile, PROFILE_ID)


def save_profile(session: Session, data: ProfileData) -> Profile:
    """Create the profile or overwrite the existing one (there is only one row)."""
    profile = get_profile(session) or Profile(id=PROFILE_ID)
    # model_dump() turns the Pydantic model into a dict of fresh values, and
    # setattr(obj, "name", value) is obj.name = value with the name in a variable
    # (like reflection's PropertyInfo.SetValue in C#)
    for field_name, value in data.model_dump().items():
        setattr(profile, field_name, value)
    profile.updated_at = utc_now()

    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def describe(profile: Profile) -> str:
    """Summary for the terminal. Shows the resume size, never its content."""
    lines = [
        f"resume:          {len(profile.resume)} chars",
        f"work modes:      {', '.join(profile.work_modes) or '-'}",
        f"cities:          {', '.join(profile.accepted_cities) or '-'}",
        f"seniority:       {', '.join(profile.seniority_levels) or '-'}",
        f"contract types:  {', '.join(profile.contract_types) or '-'}",
        f"salary:          {profile.salary_expectation or '-'}",
        f"excluded words:  {', '.join(profile.excluded_title_words) or '-'}",
        f"updated at:      {profile.updated_at:%Y-%m-%d %H:%M} UTC",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.profile")
    commands = parser.add_subparsers(dest="command", required=True)

    import_command = commands.add_parser("import", help="load profile.toml into the database")
    import_command.add_argument("path", nargs="?", type=Path, default=DEFAULT_PROFILE_PATH)

    commands.add_parser("show", help="show the saved profile (without the resume text)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    init_db()

    with Session(engine) as session:
        if args.command == "import":
            if not args.path.exists():
                raise SystemExit(f"File not found: {args.path} (copy profile.example.toml)")
            profile = save_profile(session, load_profile_file(args.path))
            print(f"Profile imported from {args.path.name}\n{describe(profile)}")

        elif args.command == "show":
            profile = get_profile(session)
            if profile is None:
                raise SystemExit("No profile yet. Run: python -m app.profile import")
            print(describe(profile))


if __name__ == "__main__":
    main()
