"""The "analyze jobs" button: score pending jobs in the background and follow the progress."""

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.db import get_session
from app.llm import LLMConfig
from app.models import JobAnalysis
from app.profile import get_profile
from app.routers.resume import require_llm_config
from app.scoring import pending_jobs, progress, score_pending, scoring_lock

router = APIRouter(prefix="/scoring", tags=["scoring"])

SessionDep = Annotated[Session, Depends(get_session)]
LLMConfigDep = Annotated[LLMConfig, Depends(require_llm_config)]

logger = logging.getLogger(__name__)


class ScoringStatus(BaseModel):
    running: bool
    analyzed: int  # jobs with a score, ever
    pending: int  # untriaged jobs that pass my filter and still have no score
    batch_total: int  # size of the current (or last) batch
    batch_done: int
    batch_failed: int
    waiting_until: datetime | None  # waiting for the free quota to refill
    stopped_reason: str | None


def build_status(session: Session) -> ScoringStatus:
    profile = get_profile(session)
    pending = len(pending_jobs(session, profile)) if profile else 0
    analyzed = session.exec(select(func.count()).select_from(JobAnalysis)).one()
    return ScoringStatus(
        running=scoring_lock.locked(),
        analyzed=analyzed,
        pending=pending,
        batch_total=progress.total,
        batch_done=progress.done,
        batch_failed=progress.failed,
        waiting_until=progress.waiting_until,
        stopped_reason=progress.stopped_reason,
    )


def score_in_background(config: LLMConfig) -> None:
    try:
        score_pending(config=config)
    except Exception:
        logger.exception("Background scoring failed")
    finally:
        scoring_lock.release()


@router.get("", response_model=ScoringStatus)
def get_scoring_status(session: SessionDep) -> ScoringStatus:
    return build_status(session)


@router.post("", response_model=ScoringStatus, status_code=status.HTTP_202_ACCEPTED)
def start_scoring(
    background_tasks: BackgroundTasks, session: SessionDep, config: LLMConfigDep
) -> ScoringStatus:
    """Score the next batch (MAX_JOBS_TO_SCORE). 202 = running; poll GET /scoring."""
    profile = get_profile(session)
    if profile is None or not profile.resume.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Add your resume on the Foco screen")
    if not scoring_lock.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Scoring is already running")

    progress.stopped_reason = None
    background_tasks.add_task(score_in_background, config)
    return build_status(session)
