from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Profile, WeighIn
from ..schemas import ProfileOut, ProfileUpdate, WeighInOut
from ..auth import CurrentUser, utcnow

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

    # N3 — Profile.weight_kg stays the current value everything else reads,
    # but a change to it is also a weigh-in. Only on an actual change: the
    # Settings screen PUTs the whole form, and re-saving an unchanged weight
    # must not fabricate a data point on the trend.
    new_weight = data.get("weight_kg")
    if new_weight is not None and new_weight != profile.weight_kg:
        db.add(WeighIn(user_id=user.id, weight_kg=new_weight, recorded_at=utcnow().replace(tzinfo=None)))

    for k, v in data.items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/weigh-ins", response_model=list[WeighInOut])
def weigh_ins(
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(90, le=365),
):
    """N3 — newest first. Fuel's trend strip reverses it for drawing."""
    return (
        db.query(WeighIn)
        .filter(WeighIn.user_id == user.id)
        .order_by(WeighIn.recorded_at.desc())
        .limit(limit)
        .all()
    )
