"""Watched company routes (Greenhouse/Lever boards)."""

from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.collect import USER_AGENT
from app.companies import (
    BoardNotFoundError,
    CompanyAlreadyWatchedError,
    add_and_fetch_company,
    company_key,
    company_stats,
    list_companies,
)
from app.db import get_session
from app.models import WatchedCompany
from app.schemas import (
    CompanyCreate,
    CompanyCreated,
    CompanyRead,
    CompanyUpdate,
    to_company_read,
)

router = APIRouter(prefix="/companies", tags=["companies"])

SessionDep = Annotated[Session, Depends(get_session)]


def get_http_client() -> Iterator[httpx.Client]:
    """One client per request, closed when the response is sent (the code after yield)."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        yield client


HttpClientDep = Annotated[httpx.Client, Depends(get_http_client)]


def get_company_or_404(session: Session, company_id: int) -> WatchedCompany:
    company = session.get(WatchedCompany, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def read_with_stats(session: Session, company: WatchedCompany) -> CompanyRead:
    stats = company_stats(session).get(company_key(company.provider, company.slug))
    return to_company_read(company, stats)


@router.get("", response_model=list[CompanyRead])
def read_companies(session: SessionDep) -> list[CompanyRead]:
    stats = company_stats(session)  # once for all companies, not once per company
    return [
        to_company_read(company, stats.get(company_key(company.provider, company.slug)))
        for company in list_companies(session)
    ]


@router.post("", response_model=CompanyCreated, status_code=status.HTTP_201_CREATED)
def create_company(
    body: CompanyCreate, session: SessionDep, client: HttpClientDep
) -> CompanyCreated:
    """Check the board exists, start watching it and save its current jobs."""
    # Unknown providers never get here: CompanyCreate.provider is a Literal (-> 422)
    try:
        added = add_and_fetch_company(session, client, body.provider, body.slug, body.name)
    except CompanyAlreadyWatchedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    except BoardNotFoundError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except (httpx.HTTPError, ValueError) as error:
        # The board's site is down or changed its format: not our fault, not the user's
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"Could not read the {body.provider} board"
        ) from error

    company = read_with_stats(session, added.company)
    return CompanyCreated(
        **company.model_dump(), found_jobs=added.found_jobs, saved_jobs=added.saved_jobs
    )


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(company_id: int, body: CompanyUpdate, session: SessionDep) -> CompanyRead:
    """Rename, or pause/resume monitoring (active=false keeps it out of the collection)."""
    company = get_company_or_404(session, company_id)

    # exclude_unset: only fields the client actually sent, so {"active": false}
    # doesn't wipe the name. Like JSON Merge Patch.
    for field_name, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(company, field_name, value.strip() if isinstance(value, str) else value)

    session.add(company)
    session.commit()
    session.refresh(company)
    return read_with_stats(session, company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, session: SessionDep) -> Response:
    """Stop watching. Jobs already collected stay (and so do their applications)."""
    company = get_company_or_404(session, company_id)
    session.delete(company)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
