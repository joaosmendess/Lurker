"""Score how well each job fits my resume (0-100) with the text AI.

Runs in batches that respect the free tier (Groq: 8,000 tokens per minute): the
prompt is kept small, and a 429 makes the batch wait what the provider asks.

Usage:
    python -m app.scoring             # score the next batch (MAX_JOBS_TO_SCORE)
    python -m app.scoring --limit 5
"""

import argparse
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.collect import USER_AGENT
from app.config import get_settings
from app.db import engine, init_db
from app.filters import filter_jobs
from app.llm import (
    LLMBadAnswerError,
    LLMConfig,
    LLMError,
    LLMRateLimitedError,
    chat,
    get_llm_config,
)
from app.models import Application, Job, JobAnalysis, Profile, utc_now
from app.profile import get_profile
from app.resume import check_invented, plain_text

# Requirements are almost always in the first part of a description; cutting here
# keeps one analysis around 3-4k tokens, about 2 jobs per minute on the free tier
MAX_JOB_CHARS = 4_000
ATTEMPTS = 2  # one retry for a malformed answer
DEFAULT_WAIT_SECONDS = 20.0  # when a 429 doesn't say how long to wait
MAX_WAIT_SECONDS = 90.0  # longer than this = the daily quota is gone: stop the batch
MAX_WAITS_PER_JOB = 5

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Você avalia o quanto uma vaga de emprego combina com um candidato, para ele decidir \
onde se candidatar. Seja realista e consistente entre vagas.

Nota de 0 a 100:
- 85 a 100: atende os requisitos centrais, nível compatível, modalidade e local aceitos;
- 70 a 84: atende a maior parte, com lacunas pequenas ou fáceis de cobrir;
- 50 a 69: encaixe parcial, faltam requisitos importantes ou o nível está acima;
- 0 a 49: pouco encaixe.

Penalize bastante: vaga presencial ou híbrida fora das cidades aceitas; senioridade \
muito acima da desejada (sênior, especialista ou lead para quem busca júnior ou pleno); \
inglês fluente ou nativo obrigatório quando o currículo não mostra isso; requisitos \
centrais que o currículo não mostra.
Não penalize a stack em si: o candidato aceita qualquer stack. Avalie pela experiência, \
nível e requisitos. Use só o que está no currículo; não suponha experiência que ele não mostra.

Responda APENAS com um objeto JSON, sem texto antes ou depois, com as chaves:
"score": inteiro de 0 a 100;
"summary": 1 ou 2 frases explicando a nota;
"matches": lista curta do que o currículo atende (itens de até 6 palavras);
"gaps": lista curta de requisitos importantes que o currículo não mostra;
"red_flags": alertas como "presencial em São Paulo", "inglês fluente obrigatório", \
"nível sênior" (lista vazia se não houver);
"pitch": 2 ou 3 frases em primeira pessoa para o candidato se apresentar a essa vaga, \
usando só fatos e termos do currículo, sem inventar nada. Não cite tecnologias, \
metodologias ou números que o currículo não tem, nem como vontade de aprender: destaque \
o que ele já tem e que a vaga pede."""


class ScoreAnswer(BaseModel):
    """The JSON the model must answer, validated like a DTO."""

    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    matches: list[str] = []
    gaps: list[str] = []
    red_flags: list[str] = []
    pitch: str = ""


def work_mode_text(remote: bool | None) -> str:
    if remote is None:
        return "não informada"
    return "remoto" if remote else "presencial ou híbrido"


def build_user_prompt(profile: Profile, job: Job) -> str:
    def listed(values: list[str]) -> str:
        return ", ".join(values) or "não informado"

    return (
        "O QUE O CANDIDATO BUSCA:\n"
        f"- senioridade: {listed(profile.seniority_levels)}\n"
        f"- modalidades aceitas: {listed(profile.work_modes)}\n"
        f"- cidades aceitas para presencial/híbrido: {listed(profile.accepted_cities)}\n"
        f"- regime: {listed(profile.contract_types)}\n"
        f"- pretensão: {profile.salary_expectation or 'não informada'}\n\n"
        f"VAGA: {job.title}\nEMPRESA: {job.company}\n"
        f"LOCAL: {job.location or 'não informado'}\nMODALIDADE: {work_mode_text(job.remote)}\n"
        f"DESCRIÇÃO:\n{job.description[:MAX_JOB_CHARS]}\n\n"
        f"CURRÍCULO:\n{profile.resume}"
    )


def parse_score(text: str) -> ScoreAnswer:
    """The JSON object inside the answer (models sometimes add a sentence or ``` around it)."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMBadAnswerError("No JSON object in the answer")
    try:
        return ScoreAnswer.model_validate(json.loads(text[start : end + 1]))
    except (ValueError, ValidationError) as error:
        # json.JSONDecodeError is a ValueError too
        raise LLMBadAnswerError(f"Invalid score JSON: {error}") from error


def analyze_job(client: httpx.Client, config: LLMConfig, profile: Profile, job: Job) -> ScoreAnswer:
    """Ask the model, retrying once on a malformed answer. Quota errors go up untouched."""
    prompt = build_user_prompt(profile, job)
    last_error: LLMBadAnswerError | None = None
    for _ in range(ATTEMPTS):
        try:
            return parse_score(plain_text(chat(client, config, SYSTEM_PROMPT, prompt)))
        except LLMBadAnswerError as error:
            last_error = error
    raise LLMError(f"No valid score for {job.id}") from last_error


def clean(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def save_analysis(
    session: Session, job: Job, answer: ScoreAnswer, resume: str, model: str
) -> JobAnalysis:
    pitch = answer.pitch.strip()
    analysis = session.get(JobAnalysis, job.id) or JobAnalysis(
        job_id=job.id, score=0, summary="", pitch="", model=""
    )
    analysis.score = answer.score
    analysis.summary = answer.summary.strip()
    analysis.matches = clean(answer.matches)
    analysis.gaps = clean(answer.gaps)
    analysis.red_flags = clean(answer.red_flags)
    analysis.pitch = pitch
    # The pitch speaks for me: same no-invention check as the tailored resume
    analysis.pitch_warnings = check_invented(resume, pitch)
    analysis.model = model
    analysis.analyzed_at = utc_now()
    session.add(analysis)
    session.commit()
    return analysis


def pending_jobs(session: Session, profile: Profile) -> list[Job]:
    """Untriaged jobs that pass my pre-filter and have no analysis yet, best bets first.

    "Best bets": jobs with one of my preferred stacks, then the newest.
    """
    has_application = select(Application.job_id)
    has_analysis = select(JobAnalysis.job_id)
    candidates = session.exec(
        select(Job).where(
            col(Job.id).not_in(has_application),  # NOT IN (subquery), like LINQ !Any()
            col(Job.id).not_in(has_analysis),
        )
    ).all()
    passed = filter_jobs(list(candidates), profile).passed
    preferred = set(profile.preferred_stack)

    def priority(job: Job) -> tuple[bool, datetime]:
        newest = job.published_at or job.collected_at
        return (bool(preferred & set(job.tags)), newest)

    # sorted with a tuple key compares item by item, like OrderBy().ThenBy()
    return sorted(passed, key=priority, reverse=True)


# --- Batch with progress ----------------------------------------------------------


@dataclass
class ScoringProgress:
    """What the UI shows while a batch runs. Only the batch thread writes to it;
    the API only reads, so plain attributes are enough (no lock needed)."""

    total: int = 0
    done: int = 0
    failed: int = 0
    waiting_until: datetime | None = None  # set while waiting for the quota
    stopped_reason: str | None = None  # why the last batch ended early, if it did


progress = ScoringProgress()

# One batch at a time per process (same idea as the collection button)
scoring_lock = threading.Lock()


@dataclass(frozen=True)
class ScoringResult:
    analyzed: int
    failed: int
    stopped_reason: str | None


def score_pending(
    db_engine: Engine = engine,
    limit: int | None = None,
    config: LLMConfig | None = None,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ScoringResult:
    """Score the next `limit` pending jobs. A failing job is logged and skipped.

    `client` and `sleep` are parameters so tests can run it without network or waiting.
    """
    config = config or get_llm_config()
    limit = limit or get_settings().max_jobs_to_score
    owns_client = client is None
    http = client or httpx.Client(headers={"User-Agent": USER_AGENT})

    analyzed = failed = 0
    stopped_reason: str | None = None
    try:
        with Session(db_engine) as session:
            profile = get_profile(session)
            if profile is None or not profile.resume.strip():
                raise ValueError("No resume in the profile")
            jobs = pending_jobs(session, profile)[:limit]
            progress.total, progress.done, progress.failed = len(jobs), 0, 0
            logger.info("Scoring %d jobs with %s", len(jobs), config.model)

            for job in jobs:
                outcome = score_one(session, http, config, profile, job, sleep)
                if outcome == "stop":
                    stopped_reason = "Cota gratuita do dia esgotada. Continua amanhã."
                    break
                if outcome == "ok":
                    analyzed += 1
                else:
                    failed += 1
                progress.done, progress.failed = analyzed, failed
    finally:
        if owns_client:
            http.close()
    progress.stopped_reason = stopped_reason
    return ScoringResult(analyzed=analyzed, failed=failed, stopped_reason=stopped_reason)


def score_one(
    session: Session,
    client: httpx.Client,
    config: LLMConfig,
    profile: Profile,
    job: Job,
    sleep: Callable[[float], None],
) -> str:
    """ "ok", "failed" (skip this job) or "stop" (quota gone: end the batch)."""
    for _ in range(MAX_WAITS_PER_JOB + 1):
        try:
            answer = analyze_job(client, config, profile, job)
        except LLMRateLimitedError as error:
            wait = error.retry_after if error.retry_after is not None else DEFAULT_WAIT_SECONDS
            if wait > MAX_WAIT_SECONDS:
                return "stop"
            logger.info("Quota: waiting %.0fs before %s", wait, job.id)
            progress.waiting_until = utc_now() + timedelta(seconds=wait)
            sleep(wait)
            progress.waiting_until = None
            continue
        except (LLMError, httpx.HTTPError) as error:
            logger.warning("Skipping %s: %s", job.id, error)
            return "failed"
        analysis = save_analysis(session, job, answer, profile.resume, config.model)
        # IDs and scores only in the logs, never the resume or the job text
        logger.info("Scored %s: %d", job.id, analysis.score)
        return "ok"
    return "stop"  # still rate limited after several waits


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="python -m app.scoring")
    parser.add_argument(
        "--limit", type=int, default=None, help="jobs to score (default: MAX_JOBS_TO_SCORE)"
    )
    args = parser.parse_args()
    init_db()
    result = score_pending(limit=args.limit)
    print(f"Scored {result.analyzed}, failed {result.failed}. {result.stopped_reason or ''}")


if __name__ == "__main__":
    main()
