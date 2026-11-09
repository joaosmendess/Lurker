"""Application routes: the kanban (create, list, move between columns, notes)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Application, ApplicationStatus, Job, StatusChange, utc_now
from app.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationRead,
    NotesUpdate,
    StatusUpdate,
    to_application_detail,
    to_application_read,
)

router = APIRouter(prefix="/applications", tags=["applications"])

SessionDep = Annotated[Session, Depends(get_session)]


def get_application_or_404(session: Session, application_id: int) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def get_job(session: Session, application: Application) -> Job:
    job = session.get(Job, application.job_id)
    if job is None:  # only possible if the job row was deleted by hand
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job of this application not found")
    return job


def record_status_change(
    session: Session, application: Application, from_status: str | None, to_status: str
) -> None:
    # application.id is set because callers flush/commit before calling this
    assert application.id is not None
    session.add(
        StatusChange(application_id=application.id, from_status=from_status, to_status=to_status)
    )


@router.post("", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, session: SessionDep) -> ApplicationRead:
    """Mark interest in a job (or discard it, with status="discarded")."""
    job = session.get(Job, body.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")

    existing = session.exec(select(Application).where(Application.job_id == body.job_id)).first()
    if existing is not None:
        # The UNIQUE constraint on job_id would also block it; this gives a clear message
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Job already has application {existing.id}"
        )

    application = Application(job_id=job.id, status=body.status, notes=body.notes)
    session.add(application)
    # flush sends the INSERT without committing, so the database assigns the id
    # we need for the history row; both are then committed together (one transaction)
    session.flush()
    record_status_change(session, application, from_status=None, to_status=application.status)
    session.commit()
    session.refresh(application)
    return to_application_read(application, job)


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    session: SessionDep,
    # alias: the URL keeps "?status=", but the Python name doesn't shadow fastapi.status
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
) -> list[ApplicationRead]:
    """All applications (the kanban), most recently moved first."""
    # Selecting two entities returns (Application, Job) tuples: one query, no N+1
    statement = select(Application, Job).join(Job, col(Application.job_id) == col(Job.id))
    if status_filter is not None:
        statement = statement.where(Application.status == status_filter)
    statement = statement.order_by(col(Application.updated_at).desc(), col(Application.id))

    return [to_application_read(application, job) for application, job in session.exec(statement)]


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, session: SessionDep) -> ApplicationDetail:
    application = get_application_or_404(session, application_id)
    history = session.exec(
        select(StatusChange)
        .where(StatusChange.application_id == application_id)
        .order_by(col(StatusChange.changed_at), col(StatusChange.id))
    ).all()
    return to_application_detail(application, get_job(session, application), list(history))


@router.patch("/{application_id}/status", response_model=ApplicationRead)
def move_application(
    application_id: int, body: StatusUpdate, session: SessionDep
) -> ApplicationRead:
    """Move the card to another kanban column. Any move is allowed, including back."""
    application = get_application_or_404(session, application_id)

    if application.status != body.status:
        record_status_change(session, application, application.status, body.status)
        application.status = body.status
        application.updated_at = utc_now()
        session.add(application)
        session.commit()
        session.refresh(application)

    return to_application_read(application, get_job(session, application))


@router.patch("/{application_id}", response_model=ApplicationRead)
def update_notes(application_id: int, body: NotesUpdate, session: SessionDep) -> ApplicationRead:
    application = get_application_or_404(session, application_id)

    application.notes = body.notes
    application.updated_at = utc_now()
    session.add(application)
    session.commit()
    session.refresh(application)

    return to_application_read(application, get_job(session, application))
