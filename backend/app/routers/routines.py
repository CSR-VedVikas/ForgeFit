from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..auth import CurrentUser
from ..db import get_db
from ..models import Routine, RoutineExercise, ExerciseCatalog
from ..schemas import RoutineCreate, RoutineUpdate, RoutineOut, RoutineExerciseOut

router = APIRouter(prefix="/api/routines", tags=["routines"])

MAX_ROUTINES = 3


def _serialize(routine: Routine) -> RoutineOut:
    items: list[RoutineExerciseOut] = []
    for re in sorted(routine.exercises, key=lambda x: x.sort_order):
        ex = re.exercise
        items.append(
            RoutineExerciseOut(
                id=re.id,
                exercise_id=re.exercise_id,
                exercise_name=ex.name if ex else "",
                body_part=ex.body_part if ex else "",
                equipment=ex.equipment if ex else "",
                image=ex.image if ex else "",
                gif_url=ex.gif_url if ex else "",
                sort_order=re.sort_order,
                default_sets=re.default_sets,
            )
        )
    return RoutineOut(
        id=routine.id,
        name=routine.name,
        created_at=routine.created_at,
        updated_at=routine.updated_at,
        exercises=items,
    )


def _load(db: Session, routine_id: int, user_id: int) -> Routine:
    routine = (
        db.query(Routine)
        .options(joinedload(Routine.exercises).joinedload(RoutineExercise.exercise))
        .filter(Routine.id == routine_id, Routine.user_id == user_id)
        .first()
    )
    if not routine:
        raise HTTPException(404, "Routine not found")
    return routine


def _replace_exercises(db: Session, routine: Routine, exercises: list) -> None:
    routine.exercises.clear()
    db.flush()
    for i, item in enumerate(exercises):
        if not db.get(ExerciseCatalog, item.exercise_id):
            raise HTTPException(400, f"Unknown exercise_id: {item.exercise_id}")
        routine.exercises.append(
            RoutineExercise(
                exercise_id=item.exercise_id,
                sort_order=i,
                default_sets=max(1, min(item.default_sets, 12)),
            )
        )


@router.get("", response_model=list[RoutineOut])
def list_routines(user: CurrentUser, db: Session = Depends(get_db)):
    rows = (
        db.query(Routine)
        .options(joinedload(Routine.exercises).joinedload(RoutineExercise.exercise))
        .filter(Routine.user_id == user.id)
        .order_by(Routine.updated_at.desc())
        .all()
    )
    return [_serialize(r) for r in rows]


@router.post("", response_model=RoutineOut)
def create_routine(payload: RoutineCreate, user: CurrentUser, db: Session = Depends(get_db)):
    count = db.query(Routine).filter(Routine.user_id == user.id).count()
    if count >= MAX_ROUTINES:
        raise HTTPException(400, f"You can save up to {MAX_ROUTINES} routines")
    routine = Routine(user_id=user.id, name=payload.name.strip())
    db.add(routine)
    db.flush()
    _replace_exercises(db, routine, payload.exercises)
    routine.updated_at = datetime.utcnow()
    db.commit()
    return _serialize(_load(db, routine.id, user.id))


@router.put("/{routine_id}", response_model=RoutineOut)
def update_routine(
    routine_id: int,
    payload: RoutineUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    routine = _load(db, routine_id, user.id)
    if payload.name is not None:
        routine.name = payload.name.strip()
    if payload.exercises is not None:
        _replace_exercises(db, routine, payload.exercises)
    routine.updated_at = datetime.utcnow()
    db.commit()
    return _serialize(_load(db, routine.id, user.id))


@router.delete("/{routine_id}")
def delete_routine(routine_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    routine = db.query(Routine).filter(Routine.id == routine_id, Routine.user_id == user.id).first()
    if not routine:
        raise HTTPException(404, "Routine not found")
    db.delete(routine)
    db.commit()
    return {"message": "Deleted"}
