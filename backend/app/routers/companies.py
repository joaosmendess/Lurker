"""Watched company routes (Greenhouse/Lever boards)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.companies import CompanyAlreadyWatchedError, add_company, list_companies
from app.db import get_session
from app.models import WatchedCompany
from app.schemas import CompanyCreate, CompanyRead, CompanyUpdate, to_company_read

router = APIRouter(prefix="/companies", tags=["companies"])

SessionDep = Annotated[Session, Depends(get_session)]


def get_company_or_404(session: Session, company_id: int) -> WatchedCompany:
    company = session.get(WatchedCompany, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("", response_model=list[CompanyRead])
def read_companies(session: SessionDep) -> list[CompanyRead]:
    return [to_company_read(company) for company in list_companies(session)]


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyCreate, session: SessionDep) -> CompanyRead:
    # Unknown providers never get here: CompanyCreate.provider is a Literal (-> 422)
    try:
        company = add_company(session, body.provider, body.slug, body.name)
    except CompanyAlreadyWatchedError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(error)) from error
    return to_company_read(company)


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
    return to_company_read(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, session: SessionDep) -> Response:
    company = get_company_or_404(session, company_id)
    session.delete(company)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
