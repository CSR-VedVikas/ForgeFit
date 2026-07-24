from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..db import get_db
from ..models import (
    WorkoutSession,
    WorkoutSet,
    FoodLog,
    Profile,
    Achievement,
    ChallengeProgress,
    PersonalRecord,
    ExerciseCatalog,
)
from ..schemas import (
    DashboardOut,
    AchievementOut,
    ChallengeOut,
    HeatmapItem,
    DailyLinkOut,
    FoodLogOut,
    ActivityOut,
    ActivityDay,
)
from ..auth import CurrentUser
from ..services.pr_engine import compute_streak, _week_start

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/daily-link", response_model=DailyLinkOut)
def daily_link(user: CurrentUser, db: Session = Depends(get_db), day: date | None = None):
    """Link today's workouts + food into one day summary."""
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    foods = (
        db.query(FoodLog)
        .filter(FoodLog.user_id == user.id, FoodLog.logged_at >= start, FoodLog.logged_at < end)
        .order_by(FoodLog.logged_at.desc())
        .all()
    )
    sessions = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user.id,
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    calories_in = sum(f.calories for f in foods)
    calories_burned = sum(s.calories_burned for s in sessions)
    volume = sum(s.total_volume for s in sessions)
    minutes = 0.0
    for s in sessions:
        if s.ended_at and s.started_at:
            minutes += max(0.0, (s.ended_at - s.started_at).total_seconds() / 60.0)

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    goal = profile.daily_calorie_goal if profile else 2200
    net = calories_in - calories_burned
    remaining = goal - net

    food_names = ", ".join(f.food_name for f in foods[:6]) or "no meals logged"
    summary = (
        f"On {day.isoformat()} you trained {len(sessions)} session(s) "
        f"({round(minutes, 1)} min, {round(volume, 0)} kg volume), "
        f"burned ~{round(calories_burned)} kcal, ate ~{round(calories_in)} kcal "
        f"({food_names}). "
        f"{'Under' if remaining >= 0 else 'Over'} goal by {abs(round(remaining))} kcal."
    )

    return DailyLinkOut(
        date=day,
        calories_in=round(calories_in, 1),
        calories_burned=round(calories_burned, 1),
        net_calories=round(net, 1),
        calorie_goal=goal,
        volume_kg=round(volume, 1),
        workout_minutes=round(minutes, 1),
        workout_count=len(sessions),
        foods=foods,
        workouts=[
            {
                "id": s.id,
                "started_at": s.started_at.isoformat(),
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "total_volume": s.total_volume,
                "calories_burned": s.calories_burned,
                "notes": s.notes,
            }
            for s in sessions
        ],
        summary=summary,
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(user: CurrentUser, db: Session = Depends(get_db)):
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)

    foods = (
        db.query(FoodLog)
        .filter(FoodLog.user_id == user.id, FoodLog.logged_at >= start, FoodLog.logged_at < end)
        .all()
    )
    calories_in = sum(f.calories for f in foods)

    sessions = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user.id,
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
        .all()
    )
    calories_burned = sum(s.calories_burned for s in sessions)
    volume_today = sum(s.total_volume for s in sessions)

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    goal = profile.daily_calorie_goal if profile else 2200

    prs = (
        db.query(PersonalRecord, ExerciseCatalog)
        .join(ExerciseCatalog, PersonalRecord.exercise_id == ExerciseCatalog.id)
        .filter(PersonalRecord.user_id == user.id)
        .order_by(PersonalRecord.achieved_at.desc())
        .limit(5)
        .all()
    )
    recent_prs = [
        {
            "exercise_id": pr.exercise_id,
            "exercise_name": ex.name,
            "record_type": pr.record_type,
            "value": pr.value,
            "achieved_at": pr.achieved_at.isoformat(),
        }
        for pr, ex in prs
    ]

    ws = _week_start()
    challenge = (
        db.query(ChallengeProgress)
        .filter(ChallengeProgress.user_id == user.id, ChallengeProgress.week_start == ws)
        .first()
    )
    challenge_out = None
    if challenge:
        pct = (challenge.current_volume / challenge.target_volume * 100) if challenge.target_volume else 0
        challenge_out = ChallengeOut(
            week_start=challenge.week_start,
            target_volume=challenge.target_volume,
            current_volume=challenge.current_volume,
            progress_pct=round(min(pct, 100), 1),
        )
    else:
        challenge_out = ChallengeOut(
            week_start=ws,
            target_volume=5000,
            current_volume=0,
            progress_pct=0,
        )

    achievements = (
        db.query(Achievement)
        .filter(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at.desc())
        .limit(8)
        .all()
    )

    return DashboardOut(
        calories_in=round(calories_in, 1),
        calories_burned=round(calories_burned, 1),
        calorie_goal=goal,
        volume_today=round(volume_today, 1),
        streak_days=compute_streak(db, user.id),
        recent_prs=recent_prs,
        challenge=challenge_out,
        recent_achievements=achievements,
    )


@router.get("/achievements", response_model=list[AchievementOut])
def achievements(user: CurrentUser, db: Session = Depends(get_db)):
    return (
        db.query(Achievement)
        .filter(Achievement.user_id == user.id)
        .order_by(Achievement.earned_at.desc())
        .limit(50)
        .all()
    )


@router.get("/heatmap", response_model=list[HeatmapItem])
def heatmap(user: CurrentUser, db: Session = Depends(get_db), days: int = 7):
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(
            ExerciseCatalog.body_part,
            func.count(WorkoutSet.id),
            func.coalesce(func.sum(WorkoutSet.volume), 0.0),
        )
        .join(WorkoutSet, WorkoutSet.exercise_id == ExerciseCatalog.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
        .filter(WorkoutSession.user_id == user.id, WorkoutSession.started_at >= since)
        .group_by(ExerciseCatalog.body_part)
        .all()
    )
    return [
        HeatmapItem(body_part=bp, set_count=int(cnt), volume=float(vol))
        for bp, cnt, vol in rows
    ]


@router.get("/volume")
def volume_stats(user: CurrentUser, db: Session = Depends(get_db), days: int = 30):
    since = datetime.utcnow() - timedelta(days=days)
    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user.id, WorkoutSession.started_at >= since)
        .order_by(WorkoutSession.started_at)
        .all()
    )
    by_day: dict[str, float] = {}
    for s in sessions:
        key = s.started_at.date().isoformat()
        by_day[key] = by_day.get(key, 0) + s.total_volume
    return {"days": [{"date": k, "volume": v} for k, v in by_day.items()]}


@router.get("/activity", response_model=ActivityOut)
def activity_stats(user: CurrentUser, db: Session = Depends(get_db), days: int = 90):
    """Profile chart: duration / volume / reps by day + this-week hours."""
    since = datetime.utcnow() - timedelta(days=days)
    sessions = (
        db.query(WorkoutSession)
        .options(joinedload(WorkoutSession.sets))
        .filter(WorkoutSession.user_id == user.id, WorkoutSession.started_at >= since)
        .order_by(WorkoutSession.started_at)
        .all()
    )
    by_day: dict[str, ActivityDay] = {}
    for s in sessions:
        key = s.started_at.date().isoformat()
        if key not in by_day:
            by_day[key] = ActivityDay(date=key)
        day = by_day[key]
        mins = 0.0
        if s.ended_at and s.started_at:
            mins = max(0.0, (s.ended_at - s.started_at).total_seconds() / 60.0)
        day.duration_min += mins
        day.volume += s.total_volume or 0
        day.reps += sum(int(st.reps or 0) for st in s.sets)

    week_start = datetime.combine(_week_start(), datetime.min.time())
    week_hours = 0.0
    for s in sessions:
        if s.started_at >= week_start and s.ended_at:
            week_hours += max(0.0, (s.ended_at - s.started_at).total_seconds() / 3600.0)

    total = db.query(WorkoutSession).filter(WorkoutSession.user_id == user.id).count()
    return ActivityOut(
        week_hours=round(week_hours, 2),
        workout_count=total,
        days=sorted(by_day.values(), key=lambda d: d.date),
    )
