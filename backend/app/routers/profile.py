"""Profile routes: read and replace my resume + preferences."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.db import get_session
from app.profile import ProfileData, get_profile, save_profile
from app.schemas import ProfileRead, to_profile_read

router = APIRouter(prefix="/profile", tags=["profile"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=ProfileRead)
def read_profile(session: SessionDep) -> ProfileRead:
    profile = get_profile(session)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No profile yet")
    return to_profile_read(profile)


# PUT (not PATCH): the client always sends the whole profile, like the TOML import.
# Same validation as profile.toml, because both use ProfileData.
@router.put("", response_model=ProfileRead)
def replace_profile(body: ProfileData, session: SessionDep) -> ProfileRead:
    return to_profile_read(save_profile(session, body))
