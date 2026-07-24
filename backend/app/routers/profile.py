from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Profile
from ..schemas import ProfileOut, ProfileUpdate
from ..auth import CurrentUser

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, user: CurrentUser, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile
