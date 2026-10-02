from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import WorkoutSession, WorkoutSet, Profile, ExerciseCatalog
from ..schemas import WorkoutCreate, WorkoutOut, SetOut, LastSessionSet
from ..auth import CurrentUser
from ..services.pr_engine import apply_prs_and_achievements
from ..services import courses as course_svc

router = APIRouter(prefix="/api/workouts", tags=["workouts"])


def _load_full(db: Session, session_id: int) -> WorkoutSession:
    return (
        db.query(WorkoutSession)
        .options(joinedload(WorkoutSession.sets).joinedload(WorkoutSet.exercise))
        .filter(WorkoutSession.id == session_id)
        .one()
    )


def _serialize_workout(session: WorkoutSession, achievements: list | None = None) -> WorkoutOut:
    sets_out: list[SetOut] = []
    for s in session.sets:
        sets_out.append(
            SetOut(
                id=s.id,
                exercise_id=s.exercise_id,
                exercise_name=s.exercise.name if s.exercise else "",
                weight_kg=s.weight_kg,
                reps=s.reps,
                set_number=s.set_number,
                volume=s.volume,
                is_pr=s.is_pr,
                pr_types=s.pr_types or [],
                gif_url=s.exercise.gif_url if s.exercise else "",
                image=s.exercise.image if s.exercise else "",
            )
        )
    return WorkoutOut(
        id=session.id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        notes=session.notes,
        total_volume=session.total_volume,
        calories_burned=session.calories_burned,
        source_query=session.source_query,
        sets=sets_out,
        new_achievements=[
            {
                "type": a.type,
                "icon_key": a.icon_key,
                "title": a.title,
                "metadata": a.metadata_json,
            }
            for a in (achievements or [])
        ],
    )


@router.post("", response_model=WorkoutOut)
def create_workout(payload: WorkoutCreate, user: CurrentUser, db: Session = Depends(get_db)):
    if not payload.sets:
        raise HTTPException(400, "At least one set required")

    # W1 — a retry after a lost response must not insert a twin. The queue
    # sends the same client_id it wrote to IndexedDB before going online, so
    # the second POST finds the first one's row. Returned without re-running
    # the PR engine: those records were already awarded.
    if payload.client_id:
        existing = (
            db.query(WorkoutSession)
            .filter(WorkoutSession.user_id == user.id, WorkoutSession.client_id == payload.client_id)
            .first()
        )
        if existing:
            return _serialize_workout(_load_full(db, existing.id))

    for s in payload.sets:
        if not db.get(ExerciseCatalog, s.exercise_id):
            raise HTTPException(400, f"Unknown exercise_id: {s.exercise_id}")

    session = WorkoutSession(
        user_id=user.id,
        client_id=payload.client_id,
        notes=payload.notes,
        source_query=payload.source_query,
        calories_burned=payload.calories_burned,
        started_at=payload.started_at or datetime.utcnow(),
        ended_at=payload.ended_at or datetime.utcnow(),
    )
    db.add(session)
    db.flush()

    for s in payload.sets:
        db.add(
            WorkoutSet(
                session_id=session.id,
                exercise_id=s.exercise_id,
                weight_kg=s.weight_kg,
                reps=s.reps,
                set_number=s.set_number,
                volume=s.weight_kg * s.reps,
            )
        )
    db.flush()
    db.refresh(session)

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    session = _load_full(db, session.id)
    achievements = apply_prs_and_achievements(db, user.id, session, profile)
    # N4 — a finished session is a course day. Same transaction as the
    # workout, so a failed commit cannot leave the cursor one day ahead.
    course_svc.advance(db, user.id)
    db.commit()
    return _serialize_workout(_load_full(db, session.id), achievements)


@router.get("", response_model=list[WorkoutOut])
def list_workouts(
    user: CurrentUser,
    db: Session = Depends(get_db),
    limit: int = Query(30, le=100),
):
    sessions = (
        db.query(WorkoutSession)
        .options(joinedload(WorkoutSession.sets).joinedload(WorkoutSet.exercise))
        .filter(WorkoutSession.user_id == user.id)
        .order_by(WorkoutSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_serialize_workout(s) for s in sessions]


@router.get("/ghost/{exercise_id}", response_model=list[LastSessionSet])
def ghost_compare(exercise_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    """Last session's sets for this exercise (for ghost compare UI)."""
    last_set = (
        db.query(WorkoutSet)
        .join(WorkoutSession)
        .filter(WorkoutSession.user_id == user.id, WorkoutSet.exercise_id == exercise_id)
        .order_by(WorkoutSession.started_at.desc())
        .first()
    )
    if not last_set:
        return []
    session_id = last_set.session_id
    sets = (
        db.query(WorkoutSet)
        .join(WorkoutSession)
        .filter(WorkoutSet.session_id == session_id, WorkoutSet.exercise_id == exercise_id)
        .order_by(WorkoutSet.set_number)
        .all()
    )
    session = db.get(WorkoutSession, session_id)
    return [
        LastSessionSet(
            weight_kg=s.weight_kg,
            reps=s.reps,
            set_number=s.set_number,
            volume=s.volume,
            logged_at=session.started_at if session else datetime.utcnow(),
        )
        for s in sets
    ]


@router.get("/{workout_id}", response_model=WorkoutOut)
def get_workout(workout_id: int, user: CurrentUser, db: Session = Depends(get_db)):
    session = (
        db.query(WorkoutSession)
        .options(joinedload(WorkoutSession.sets).joinedload(WorkoutSet.exercise))
        .filter(WorkoutSession.id == workout_id, WorkoutSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(404, "Workout not found")
    return _serialize_workout(session)
