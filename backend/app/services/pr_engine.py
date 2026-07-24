from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import (
    WorkoutSession,
    WorkoutSet,
    PersonalRecord,
    Achievement,
    ChallengeProgress,
    Profile,
    ExerciseCatalog,
)


ICON_MAP = {
    "new_pr_weight": "pr-weight",
    "new_pr_volume": "pr-volume",
    "new_pr_reps": "pr-reps",
    "first_workout": "first-fire",
    "first_log_exercise": "first-log",
    "streak_7": "streak-7",
    "challenge_complete": "challenge",
}


def effective_weight(weight_kg: float, profile: Profile | None, exercise: ExerciseCatalog | None) -> float:
    if weight_kg and weight_kg > 0:
        return weight_kg
    if exercise and exercise.equipment == "body weight" and profile:
        return profile.weight_kg
    return weight_kg or 0.0


def apply_prs_and_achievements(
    db: Session,
    user_id: int,
    session: WorkoutSession,
    profile: Profile | None,
) -> list[Achievement]:
    """Compute volumes, detect PRs once per exercise/metric, emit achievements."""
    new_achievements: list[Achievement] = []

    prior_count = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id, WorkoutSession.id != session.id)
        .count()
    )
    if prior_count == 0:
        new_achievements.append(
            Achievement(
                user_id=user_id,
                type="first_workout",
                icon_key=ICON_MAP["first_workout"],
                title="First Forge — workout logged",
                metadata_json={"session_id": session.id},
            )
        )

    # Deduplicate collection in case of joinedload quirks
    sets = list({s.id: s for s in session.sets}.values())

    # Fill volumes + collect best metrics for this session
    # key: (exercise_id, record_type) -> (value, workout_set)
    best: dict[tuple[str, str], tuple[float, WorkoutSet]] = {}
    seen_exercises: set[str] = set()

    for s in sets:
        exercise = db.get(ExerciseCatalog, s.exercise_id)
        w = effective_weight(s.weight_kg, profile, exercise)
        vol = w * s.reps
        s.volume = vol
        if s.weight_kg == 0 and w > 0:
            s.weight_kg = w
        s.is_pr = False
        s.pr_types = []

        for record_type, value in (
            ("max_weight", w),
            ("max_reps", float(s.reps)),
            ("max_volume", vol),
        ):
            if value <= 0:
                continue
            key = (s.exercise_id, record_type)
            prev = best.get(key)
            if prev is None or value > prev[0]:
                best[key] = (value, s)

        if s.exercise_id not in seen_exercises:
            seen_exercises.add(s.exercise_id)
            prior_sets = (
                db.query(WorkoutSet)
                .join(WorkoutSession)
                .filter(
                    WorkoutSession.user_id == user_id,
                    WorkoutSet.exercise_id == s.exercise_id,
                    WorkoutSet.session_id != session.id,
                )
                .count()
            )
            if prior_sets == 0:
                new_achievements.append(
                    Achievement(
                        user_id=user_id,
                        type="first_log_exercise",
                        icon_key=ICON_MAP["first_log_exercise"],
                        title=f"New movement: {exercise.name if exercise else s.exercise_id}",
                        metadata_json={"exercise_id": s.exercise_id},
                    )
                )

    # Load existing PRs for touched exercises only
    exercise_ids = list({ex_id for ex_id, _ in best})
    existing_rows = (
        db.query(PersonalRecord)
        .filter(
            PersonalRecord.user_id == user_id,
            PersonalRecord.exercise_id.in_(exercise_ids) if exercise_ids else False,
        )
        .all()
        if exercise_ids
        else []
    )
    existing_map = {(r.exercise_id, r.record_type): r for r in existing_rows}

    for (exercise_id, record_type), (value, s) in best.items():
        key = (exercise_id, record_type)
        row = existing_map.get(key)
        if row is None:
            # Re-check DB in case of stale session / prior partial writes
            row = (
                db.query(PersonalRecord)
                .filter(
                    PersonalRecord.user_id == user_id,
                    PersonalRecord.exercise_id == exercise_id,
                    PersonalRecord.record_type == record_type,
                )
                .first()
            )
        if row is None:
            row = PersonalRecord(
                user_id=user_id,
                exercise_id=exercise_id,
                record_type=record_type,
                value=value,
                achieved_at=datetime.utcnow(),
                workout_set_id=s.id,
            )
            db.add(row)
            existing_map[key] = row
            is_pr = True
        elif value > row.value:
            row.value = value
            row.achieved_at = datetime.utcnow()
            row.workout_set_id = s.id
            is_pr = True
        else:
            is_pr = False

        if is_pr:
            types = list(s.pr_types or [])
            if record_type not in types:
                types.append(record_type)
            s.pr_types = types
            s.is_pr = True
            exercise = db.get(ExerciseCatalog, exercise_id)
            pr_key = {
                "max_weight": "new_pr_weight",
                "max_reps": "new_pr_reps",
                "max_volume": "new_pr_volume",
            }[record_type]
            new_achievements.append(
                Achievement(
                    user_id=user_id,
                    type=pr_key,
                    icon_key=ICON_MAP[pr_key],
                    title=f"PR {record_type.replace('_', ' ')} — {exercise.name if exercise else exercise_id}",
                    metadata_json={
                        "exercise_id": exercise_id,
                        "value": value,
                        "record_type": record_type,
                    },
                )
            )

    for ach in new_achievements:
        db.add(ach)

    session.total_volume = sum(x.volume for x in sets)
    _update_challenge(db, user_id, session.total_volume, new_achievements)
    _check_streak(db, user_id, new_achievements)
    db.flush()
    return new_achievements


def _week_start(d: date | None = None) -> date:
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def _update_challenge(
    db: Session,
    user_id: int,
    added_volume: float,
    new_achievements: list[Achievement],
) -> None:
    ws = _week_start()
    challenge = (
        db.query(ChallengeProgress)
        .filter(ChallengeProgress.user_id == user_id, ChallengeProgress.week_start == ws)
        .first()
    )
    if not challenge:
        last_ws = ws - timedelta(days=7)
        last = (
            db.query(ChallengeProgress)
            .filter(ChallengeProgress.user_id == user_id, ChallengeProgress.week_start == last_ws)
            .first()
        )
        if last and last.current_volume > 0:
            target = last.current_volume * 1.05
        else:
            start = datetime.combine(last_ws, datetime.min.time())
            end = datetime.combine(ws, datetime.min.time())
            prev_vol = (
                db.query(func.coalesce(func.sum(WorkoutSession.total_volume), 0.0))
                .filter(
                    WorkoutSession.user_id == user_id,
                    WorkoutSession.started_at >= start,
                    WorkoutSession.started_at < end,
                )
                .scalar()
            )
            target = max(float(prev_vol) * 1.05, 5000.0)
        challenge = ChallengeProgress(
            user_id=user_id,
            week_start=ws,
            target_volume=round(target, 1),
            current_volume=0.0,
        )
        db.add(challenge)

    was_complete = challenge.current_volume >= challenge.target_volume > 0
    challenge.current_volume += added_volume
    if not was_complete and challenge.current_volume >= challenge.target_volume > 0:
        ach = Achievement(
            user_id=user_id,
            type="challenge_complete",
            icon_key=ICON_MAP["challenge_complete"],
            title="Weekly volume challenge crushed",
            metadata_json={"week_start": str(ws), "volume": challenge.current_volume},
        )
        db.add(ach)
        new_achievements.append(ach)


def _check_streak(db: Session, user_id: int, new_achievements: list[Achievement]) -> None:
    sessions = (
        db.query(WorkoutSession.started_at)
        .filter(WorkoutSession.user_id == user_id)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    days = sorted({s.started_at.date() for s in sessions}, reverse=True)
    streak = 0
    cursor = date.today()
    for d in days:
        if d == cursor:
            streak = max(streak, 1)
            continue
        if streak == 0 and d == date.today() - timedelta(days=1):
            streak = 1
            cursor = d
            continue
        if d == cursor - timedelta(days=1):
            streak += 1
            cursor = d
        else:
            break

    if streak >= 7:
        exists = (
            db.query(Achievement)
            .filter(Achievement.user_id == user_id, Achievement.type == "streak_7")
            .first()
        )
        if not exists:
            ach = Achievement(
                user_id=user_id,
                type="streak_7",
                icon_key=ICON_MAP["streak_7"],
                title="7-day forge streak",
                metadata_json={"streak": streak},
            )
            db.add(ach)
            new_achievements.append(ach)


def compute_streak(db: Session, user_id: int) -> int:
    sessions = (
        db.query(WorkoutSession.started_at)
        .filter(WorkoutSession.user_id == user_id)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    days = sorted({s.started_at.date() for s in sessions}, reverse=True)
    if not days:
        return 0
    if days[0] not in (date.today(), date.today() - timedelta(days=1)):
        return 0
    streak = 0
    cursor = days[0]
    for d in days:
        if d == cursor:
            streak += 1 if streak == 0 else 0
            if streak == 0:
                streak = 1
            continue
        if d == cursor - timedelta(days=1):
            streak += 1
            cursor = d
        else:
            break
    # recount properly
    streak = 1
    cursor = days[0]
    for d in days[1:]:
        if d == cursor - timedelta(days=1):
            streak += 1
            cursor = d
        elif d == cursor:
            continue
        else:
            break
    return streak
