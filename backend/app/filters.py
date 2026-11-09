"""Cheap pre-filter that runs before the AI, so we don't pay to score obvious misses.

Report on the jobs in the database (read-only):
    python -m app.filters
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Job, Profile
from app.profile import get_profile


# frozen=True makes instances immutable (like a C# record with init-only props)
@dataclass(frozen=True)
class FilterResult:
    passed: list[Job]
    # (job, reason) pairs, so every discard can be audited
    rejected: list[tuple[Job, str]]


def normalize(text: str) -> str:
    """Lowercase and strip accents: "Estágio" -> "estagio", "Maceió" -> "maceio"."""
    # NFKD splits "á" into "a" + a combining accent mark; then we drop the marks
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def find_excluded_word(title: str, excluded_words: list[str]) -> str | None:
    """Return the first excluded word found in the title as a whole word, or None."""
    normalized_title = normalize(title)
    for word in excluded_words:
        # Whole-word match: "intern" matches "Intern" but not "Internal".
        # (?<!\w) / (?!\w) = "no letter/digit right before / after". Plain \b would
        # fail for words ending in a symbol, like "c++" at the end of a title.
        pattern = rf"(?<!\w){re.escape(normalize(word))}(?!\w)"
        if re.search(pattern, normalized_title):
            return word
    return None


def is_in_accepted_city(location: str | None, accepted_cities: list[str]) -> bool:
    if not location:
        return False
    normalized_location = normalize(location)
    return any(normalize(city) in normalized_location for city in accepted_cities)


def work_mode_rejection(job: Job, profile: Profile) -> str | None:
    """Return why the job's work mode doesn't fit the profile, or None if it fits."""
    if job.remote is True:
        if "remote" in profile.work_modes:
            return None
        return "remote job, but remote is not accepted"

    if job.remote is False:
        # Job.remote doesn't tell hybrid from onsite, so accepting either is enough
        accepts_in_person = "hybrid" in profile.work_modes or "onsite" in profile.work_modes
        if not accepts_in_person:
            return "hybrid/onsite job, but only remote is accepted"
        if not is_in_accepted_city(job.location, profile.accepted_cities):
            return f"hybrid/onsite outside accepted cities ({job.location or 'no location'})"
        return None

    # remote is None: unknown. By default the AI reads the description and decides.
    if profile.strict_unknown_work_mode and names_other_city(job.location, profile):
        return f"unknown work mode, located outside accepted cities ({job.location})"
    return None


# Locations that name a country or region, not a city: they don't imply in-person
# work (e.g. QuintoAndar lists remote-first jobs as just "Brasil")
BROAD_LOCATIONS: frozenset[str] = frozenset(
    {
        "brasil",
        "brazil",
        "latam",
        "latin america",
        "america latina",
        "americas",
        "worldwide",
        "anywhere",
        "global",
        "south america",
        "america do sul",
    }
)


def names_other_city(location: str | None, profile: Profile) -> bool:
    """True when the location points to a specific place outside the accepted cities."""
    if not location:
        return False
    normalized = normalize(location).strip(" .,")
    if normalized in BROAD_LOCATIONS or "remot" in normalized:
        return False
    return not is_in_accepted_city(location, profile.accepted_cities)


def rejection_reason(job: Job, profile: Profile) -> str | None:
    """Why the job should be discarded before the AI, or None to keep it."""
    excluded_word = find_excluded_word(job.title, profile.excluded_title_words)
    if excluded_word is not None:
        return f"title contains '{excluded_word}'"
    return work_mode_rejection(job, profile)


def filter_jobs(jobs: list[Job], profile: Profile) -> FilterResult:
    passed: list[Job] = []
    rejected: list[tuple[Job, str]] = []
    for job in jobs:
        reason = rejection_reason(job, profile)
        if reason is None:
            passed.append(job)
        else:
            rejected.append((job, reason))
    return FilterResult(passed=passed, rejected=rejected)


def summarize_reason(reason: str) -> str:
    """Group similar reasons for the report (drops the city/location detail)."""
    return reason.split(" (")[0]


def main() -> None:
    init_db()
    with Session(engine) as session:
        profile = get_profile(session)
        if profile is None:
            raise SystemExit("No profile yet. Run: python -m app.profile import")
        jobs = list(session.exec(select(Job)).all())

    result = filter_jobs(jobs, profile)
    print(f"{len(jobs)} jobs -> {len(result.passed)} pass, {len(result.rejected)} rejected\n")

    print("Rejected by reason:")
    reasons = Counter(summarize_reason(reason) for _, reason in result.rejected)
    for reason, count in reasons.most_common():
        print(f"  {count:>5}  {reason}")

    print("\nPassed by source / remote:")
    for (source, remote), count in Counter((j.source, j.remote) for j in result.passed).items():
        print(f"  {count:>5}  {source:<10} remote={remote}")


if __name__ == "__main__":
    main()
