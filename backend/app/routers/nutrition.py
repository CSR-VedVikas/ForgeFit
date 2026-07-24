from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import FoodLog, WorkoutSession, Profile
from ..schemas import FoodLogCreate, FoodLogOut, DailyNutrition
from ..auth import CurrentUser

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.post("/log", response_model=FoodLogOut)
def log_food(payload: FoodLogCreate, user: CurrentUser, db: Session = Depends(get_db)):
    entry = FoodLog(
        user_id=user.id,
        query_text=payload.query_text,
        food_name=payload.food_name,
        calories=payload.calories,
        protein=payload.protein,
        carbs=payload.carbs,
        fat=payload.fat,
        meal_type=payload.meal_type,
        source_confidence=payload.source_confidence,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/log/batch", response_model=list[FoodLogOut])
def log_food_batch(payload: list[FoodLogCreate], user: CurrentUser, db: Session = Depends(get_db)):
    entries = []
    for item in payload:
        entry = FoodLog(
            user_id=user.id,
            query_text=item.query_text,
            food_name=item.food_name,
            calories=item.calories,
            protein=item.protein,
            carbs=item.carbs,
            fat=item.fat,
            meal_type=item.meal_type,
            source_confidence=item.source_confidence,
        )
        db.add(entry)
        entries.append(entry)
    db.commit()
    for e in entries:
        db.refresh(e)
    return entries


@router.get("/daily", response_model=DailyNutrition)
def daily(user: CurrentUser, db: Session = Depends(get_db), day: date | None = None):
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    foods = (
        db.query(FoodLog)
        .filter(FoodLog.user_id == user.id, FoodLog.logged_at >= start, FoodLog.logged_at < end)
        .order_by(FoodLog.logged_at.desc())
        .all()
    )
    calories_in = sum(f.calories for f in foods)
    protein = sum(f.protein for f in foods)
    carbs = sum(f.carbs for f in foods)
    fat = sum(f.fat for f in foods)

    burned = (
        db.query(func.coalesce(func.sum(WorkoutSession.calories_burned), 0.0))
        .filter(
            WorkoutSession.user_id == user.id,
            WorkoutSession.started_at >= start,
            WorkoutSession.started_at < end,
        )
        .scalar()
    )
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    goal = profile.daily_calorie_goal if profile else 2200

    return DailyNutrition(
        date=day,
        calories_in=round(calories_in, 1),
        protein=round(protein, 1),
        carbs=round(carbs, 1),
        fat=round(fat, 1),
        calories_burned=round(float(burned), 1),
        calorie_goal=goal,
        foods=foods,
    )
