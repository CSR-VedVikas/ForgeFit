"""The user's calendar (app/clock.py) and the Smart Log fallback.

The day-boundary tests reproduce the bug that surfaced at 01:14 IST on
3 Oct 2026: rows stamped 19:44 UTC on the 2nd belong to the 3rd in India.
"""

import asyncio
from datetime import date, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import RateLimitError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.clock import UserClock, resolve, to_naive_utc
from app.db import Base, get_db
from app.main import app
from app.models import ExerciseCatalog, FoodLog, WorkoutSession, WaterLog
from app.services import openai_nlp
from app.services.pr_engine import compute_streak

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

IST = {"X-Timezone": "Asia/Kolkata"}


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    s = TestingSessionLocal()
    s.add(ExerciseCatalog(
        id="0025", name="barbell bench press", category="chest", body_part="chest",
        equipment="barbell", target="pectorals", muscle_group="chest", secondary_muscles=[],
        instructions_en="", instruction_steps_en=[], image="", gif_url="", attribution="",
    ))
    s.commit()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override():
        yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    r = client.post("/api/auth/register", json={"email": "c@test.com", "password": "password1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def user_id(db):
    from app.models import User
    return db.query(User).one().id


# ── UserClock ────────────────────────────────────────────────────────

def test_ist_day_starts_at_1830_utc_the_day_before():
    start, end = resolve("Asia/Kolkata").day_bounds(date(2026, 10, 3))
    assert start == datetime(2026, 10, 2, 18, 30)
    assert end == datetime(2026, 10, 3, 18, 30)


def test_local_date_of_the_row_that_triggered_the_bug():
    assert resolve("Asia/Kolkata").local_date(datetime(2026, 10, 2, 19, 44)) == date(2026, 10, 3)
    assert UserClock().local_date(datetime(2026, 10, 2, 19, 44)) == date(2026, 10, 2)


def test_dst_day_is_23_hours_not_24():
    start, end = resolve("Europe/London").day_bounds(date(2026, 3, 29))  # clocks go forward
    assert (end - start).total_seconds() == 23 * 3600


@pytest.mark.parametrize("bad", [None, "", "Mars/Olympus", "../../etc/passwd", "x" * 200])
def test_unknown_or_hostile_zone_falls_back_to_utc(bad):
    assert resolve(bad).name == "UTC"


def test_aware_client_timestamp_is_stored_as_naive_utc():
    from datetime import timezone, timedelta
    aware = datetime(2026, 10, 3, 1, 14, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert to_naive_utc(aware) == datetime(2026, 10, 2, 19, 44)


# ── endpoints honour X-Timezone ──────────────────────────────────────

def test_late_night_meal_lands_on_the_users_today_not_utcs(client, auth, db):
    db.add(FoodLog(user_id=user_id(db), food_name="late snack", calories=300,
                   logged_at=datetime(2026, 10, 2, 19, 44)))
    db.commit()

    ist = client.get("/api/nutrition/daily?day=2026-10-03", headers={**auth, **IST}).json()
    assert ist["calories_in"] == 300

    utc = client.get("/api/nutrition/daily?day=2026-10-03", headers=auth).json()
    assert utc["calories_in"] == 0


def test_water_and_daily_link_use_the_same_window(client, auth, db):
    uid = user_id(db)
    db.add(WaterLog(user_id=uid, ml=500, logged_at=datetime(2026, 10, 2, 19, 0)))
    db.add(WorkoutSession(user_id=uid, started_at=datetime(2026, 10, 2, 20, 0),
                          ended_at=datetime(2026, 10, 2, 21, 0), calories_burned=250))
    db.commit()
    water = client.get("/api/nutrition/water?day=2026-10-03", headers={**auth, **IST}).json()
    assert [w["ml"] for w in water] == [500]
    link = client.get("/api/stats/daily-link?day=2026-10-03", headers={**auth, **IST}).json()
    assert link["calories_burned"] == 250


def test_streak_counts_the_users_days(db, client, auth):
    uid = user_id(db)
    # 23:00 and 01:00 IST on consecutive local days — one UTC day apart only
    # by accident. In UTC both fall on the 2nd; in IST they are the 2nd and 3rd.
    for h in (17, 19):
        db.add(WorkoutSession(user_id=uid, started_at=datetime(2026, 10, 2, h, 30)))
    db.commit()

    class FrozenIST(UserClock):
        def today(self):
            return date(2026, 10, 3)

    class FrozenUTC(UserClock):
        def today(self):
            return date(2026, 10, 2)

    from zoneinfo import ZoneInfo
    assert compute_streak(db, uid, FrozenIST(ZoneInfo("Asia/Kolkata"))) == 2
    assert compute_streak(db, uid, FrozenUTC()) == 1


def test_workout_with_aware_timestamps_is_stored_naive_utc(client, auth, db):
    r = client.post("/api/workouts", headers={**auth, **IST}, json={
        "started_at": "2026-10-03T01:14:00+05:30",
        "ended_at": "2026-10-03T02:00:00+05:30",
        "sets": [{"exercise_id": "0025", "weight_kg": 60, "reps": 5}],
    })
    assert r.status_code == 200
    s = db.query(WorkoutSession).one()
    assert s.started_at == datetime(2026, 10, 2, 19, 44) and s.started_at.tzinfo is None


# ── Smart Log survives OpenAI failing ────────────────────────────────

class _Failing:
    """Stands in for AsyncOpenAI with an empty balance."""
    class chat:
        class completions:
            @staticmethod
            async def create(**kw):
                req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
                raise RateLimitError("insufficient_quota", response=httpx.Response(429, request=req), body=None)


def test_strength_parse_falls_back_to_regex_when_openai_fails(monkeypatch):
    monkeypatch.setattr(openai_nlp, "_client", lambda: _Failing())
    out = asyncio.run(openai_nlp.parse_strength_sets("bench press 3x8 at 60kg"))
    assert out["sets"], "fallback produced no sets"
    s = out["sets"][0]
    assert (s["weight_kg"], s["reps"]) == (60, 8)


def test_intent_classify_falls_back_too(monkeypatch):
    monkeypatch.setattr(openai_nlp, "_client", lambda: _Failing())
    out = asyncio.run(openai_nlp.classify_intent("bench press 3x8 at 60kg"))
    assert out.get("intent")
