"""Resume tailored to a job by the text AI, plus whether the AI is configured."""

from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.http_client import get_http_client
from app.llm import LLMConfig, LLMError, LLMNotConfiguredError, LLMRateLimitedError, get_llm_config
from app.models import Job, TailoredResume
from app.profile import get_profile
from app.resume import tailor_resume
from app.schemas import LLMStatus, TailoredResumeRead, column_values

router = APIRouter(prefix="/jobs/{job_id}/resume", tags=["resume"])
status_router = APIRouter(prefix="/llm", tags=["resume"])

SessionDep = Annotated[Session, Depends(get_session)]
HttpClientDep = Annotated[httpx.Client, Depends(get_http_client)]


def require_llm_config() -> LLMConfig:
    """The AI settings, or 503 telling what's missing. Tests override this dependency."""
    try:
        return get_llm_config()
    except LLMNotConfiguredError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


LLMConfigDep = Annotated[LLMConfig, Depends(require_llm_config)]


def get_job_or_404(session: Session, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def to_read(tailored: TailoredResume) -> TailoredResumeRead:
    return TailoredResumeRead.model_validate(column_values(tailored))


@router.get("", response_model=TailoredResumeRead)
def read_tailored_resume(job_id: str, session: SessionDep) -> TailoredResumeRead:
    """The last version generated for this job. 404 = never generated."""
    get_job_or_404(session, job_id)
    tailored = session.get(TailoredResume, job_id)
    if tailored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No tailored resume yet")
    return to_read(tailored)


@router.post("", response_model=TailoredResumeRead)
def create_tailored_resume(
    job_id: str, session: SessionDep, client: HttpClientDep, config: LLMConfigDep
) -> TailoredResumeRead:
    """Ask the AI for a version of my resume for this job (replaces the previous one)."""
    job = get_job_or_404(session, job_id)
    profile = get_profile(session)
    if profile is None or not profile.resume.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Add your resume on the Foco screen")

    try:
        tailored = tailor_resume(session, client, config, profile.resume, job)
    except LLMRateLimitedError as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)) from error
    except (LLMError, httpx.HTTPError) as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return to_read(tailored)


@status_router.get("/status", response_model=LLMStatus)
def read_llm_status() -> LLMStatus:
    """Whether the AI is set up (never returns the key itself)."""
    settings = get_settings()
    has_key = bool(settings.llm_api_key.get_secret_value())
    return LLMStatus(
        configured=has_key and bool(settings.llm_model),
        has_key=has_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
