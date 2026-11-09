"""The "collect now" button: start a collection in the background and check its status."""

import logging
import threading
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.collect import latest_run, run_collection
from app.config import get_settings
from app.db import get_session
from app.models import CollectRun, utc_now
from app.schemas import column_values
from app.sources.base import as_utc

router = APIRouter(prefix="/collect", tags=["collect"])

SessionDep = Annotated[Session, Depends(get_session)]

logger = logging.getLogger(__name__)

# One collection at a time per process. A Lock is like C#'s SemaphoreSlim(1, 1):
# acquire(blocking=False) is TryEnter, it never waits.
_collect_lock = threading.Lock()


class CollectRunRead(BaseModel):
    id: int
    started_at: datetime
    finished_at: datetime | None
    fetched: int
    saved: int
    failed_sources: list[str]
    error: str | None


class CollectStatus(BaseModel):
    running: bool
    # When the cooldown ends; None means "collect now" is allowed right away
    cooldown_until: datetime | None
    last_run: CollectRunRead | None


def cooldown_until(last_run: CollectRun | None) -> datetime | None:
    if last_run is None:
        return None
    started_at = as_utc(last_run.started_at)
    assert started_at is not None
    ends_at = started_at + timedelta(minutes=get_settings().collect_cooldown_minutes)
    return ends_at if ends_at > utc_now() else None


def build_status(session: Session) -> CollectStatus:
    last_run = latest_run(session)
    return CollectStatus(
        running=_collect_lock.locked(),
        cooldown_until=cooldown_until(last_run),
        last_run=CollectRunRead.model_validate(column_values(last_run)) if last_run else None,
    )


def collect_in_background() -> None:
    """Runs after the response is sent. Releases the lock taken by the endpoint."""
    try:
        run_collection()
    except Exception:
        # Already recorded in CollectRun.error; log it so it also shows in the console
        logger.exception("Background collection failed")
    finally:
        # finally runs whether the try succeeded or raised, like C#'s finally
        _collect_lock.release()


@router.get("", response_model=CollectStatus)
def get_collect_status(session: SessionDep) -> CollectStatus:
    return build_status(session)


@router.post("", response_model=CollectStatus, status_code=status.HTTP_202_ACCEPTED)
def start_collection(background_tasks: BackgroundTasks, session: SessionDep) -> CollectStatus:
    """Start a collection. 202 = accepted and running; poll GET /collect to see the result."""
    blocked_until = cooldown_until(latest_run(session))
    if blocked_until is not None:
        seconds_left = int((blocked_until - utc_now()).total_seconds()) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Last collection was recent. Try again after {blocked_until:%H:%M} UTC.",
            headers={"Retry-After": str(seconds_left)},
        )

    # Taken here (not inside the task) so two quick clicks can't both pass the check
    if not _collect_lock.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A collection is already running")

    # BackgroundTasks runs the function after the response is sent (in a worker
    # thread, since it's sync), so the request returns immediately.
    background_tasks.add_task(collect_in_background)
    return build_status(session)
