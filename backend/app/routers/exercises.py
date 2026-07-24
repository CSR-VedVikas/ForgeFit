from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ExerciseCatalog
from ..schemas import ExerciseOut, ExerciseListItem
from ..auth import CurrentUser

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseListItem])
def list_exercises(
    user: CurrentUser,
    db: Session = Depends(get_db),
    q: str | None = None,
    body_part: str | None = None,
    equipment: str | None = None,
    target: str | None = None,
    limit: int = Query(48, le=200),
    offset: int = 0,
):
    query = db.query(ExerciseCatalog)
    if q:
        query = query.filter(ExerciseCatalog.name.ilike(f"%{q}%"))
    if body_part:
        query = query.filter(ExerciseCatalog.body_part == body_part.lower())
    if equipment:
        query = query.filter(ExerciseCatalog.equipment == equipment.lower())
    if target:
        query = query.filter(ExerciseCatalog.target == target.lower())
    return query.order_by(ExerciseCatalog.name).offset(offset).limit(limit).all()


@router.get("/meta/filters")
def filters(user: CurrentUser, db: Session = Depends(get_db)):
    body_parts = [r[0] for r in db.query(ExerciseCatalog.body_part).distinct().order_by(ExerciseCatalog.body_part)]
    equipment = [r[0] for r in db.query(ExerciseCatalog.equipment).distinct().order_by(ExerciseCatalog.equipment)]
    return {"body_parts": body_parts, "equipment": equipment}


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    ex = db.get(ExerciseCatalog, exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    return ex
