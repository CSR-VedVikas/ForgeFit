from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import FoodLog, WorkoutSession, Profile, WaterLog
from ..schemas import (
    FoodLogCreate,
    FoodLogOut,
    DailyNutrition,
    WaterLogCreate,
    WaterLogOut,
    BarcodeItem,
)
from ..auth import CurrentUser
from ..config import get_settings
from ..rate_limit import limiter
from ..services.nutrition_api import product_by_barcode, NutritionAPIError

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])
settings = get_settings()

# N2 — 35 ml per kg of body weight, the figure the Fuel screen was designed to.
WATER_ML_PER_KG = 35


def _entry_from(payload: FoodLogCreate, user_id: int) -> FoodLog:
    return FoodLog(
        user_id=user_id,
        query_text=payload.query_text,
        food_name=payload.food_name,
        calories=payload.calories,
        protein=payload.protein,
        carbs=payload.carbs,
        fat=payload.fat,
        meal_type=payload.meal_type,
        source_confidence=payload.source_confidence,
        # N1 — these used to stop here.
        quantity=payload.quantity,
        unit=payload.unit or "",
    )


def _day_bounds(day: date | None) -> tuple[date, datetime, datetime]:
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    return day, start, start + timedelta(days=1)


@router.post("/log", response_model=FoodLogOut)
def log_food(payload: FoodLogCreate, user: CurrentUser, db: Session = Depends(get_db)):
    entry = _entry_from(payload, user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/log/batch", response_model=list[FoodLogOut])
def log_food_batch(payload: list[FoodLogCreate], user: CurrentUser, db: Session = Depends(get_db)):
    entries = [_entry_from(item, user.id) for item in payload]
    db.add_all(entries)
    db.commit()
    for e in entries:
        db.refresh(e)
    return entries


@router.post("/water", response_model=WaterLogOut)
def log_water(payload: WaterLogCreate, user: CurrentUser, db: Session = Depends(get_db)):
    """N2 — one tap on the water tile. The tile sends its increment (250 ml
    by default); this does not accumulate, it appends."""
    row = WaterLog(user_id=user.id, ml=payload.ml)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/water", response_model=list[WaterLogOut])
def list_water(user: CurrentUser, db: Session = Depends(get_db), day: date | None = None):
    _, start, end = _day_bounds(day)
    return (
        db.query(WaterLog)
        .filter(WaterLog.user_id == user.id, WaterLog.logged_at >= start, WaterLog.logged_at < end)
        .order_by(WaterLog.logged_at.desc())
        .all()
    )


@router.get("/barcode/{upc}", response_model=BarcodeItem)
@limiter.limit(settings.rate_limit_nlp)
async def barcode(request: Request, upc: str, user: CurrentUser):
    """N5 — look a packaged product up by UPC/EAN. Hits the provider's item
    endpoint, which is separate from natural/nutrients; the result is shaped
    like a DraftFood so the portion editor treats it the same as a parsed
    entry. The frontend's pre-permission explainer runs before the scanner,
    not here."""
    upc = "".join(ch for ch in upc if ch.isdigit())
    if not 8 <= len(upc) <= 14:
        raise HTTPException(400, "A barcode is 8 to 14 digits")
    try:
        item = await product_by_barcode(upc)
    except NutritionAPIError as e:
        raise HTTPException(502, str(e))
    if not item:
        raise HTTPException(404, "No product matches that barcode")
    return BarcodeItem(upc=upc, **item)


@router.get("/daily", response_model=DailyNutrition)
def daily(user: CurrentUser, db: Session = Depends(get_db), day: date | None = None):
    day, start, end = _day_bounds(day)

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
    water = (
        db.query(func.coalesce(func.sum(WaterLog.ml), 0))
        .filter(WaterLog.user_id == user.id, WaterLog.logged_at >= start, WaterLog.logged_at < end)
        .scalar()
    )
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    goal = profile.daily_calorie_goal if profile else 2200
    weight = profile.weight_kg if profile else 75.0

    return DailyNutrition(
        date=day,
        calories_in=round(calories_in, 1),
        protein=round(protein, 1),
        carbs=round(carbs, 1),
        fat=round(fat, 1),
        calories_burned=round(float(burned), 1),
        calorie_goal=goal,
        foods=foods,
        water_ml=int(water),
        water_goal_ml=int(round(weight * WATER_ML_PER_KG)),
    )
