"""Migration 0003 — one test per schema gap.

N1 portions persist · N2 water · N3 weigh-in history · N4 courses ·
N5 barcode lookup · R1 routine prescription · W1 idempotent workout create
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ExerciseCatalog, Course, WorkoutSession, WeighIn

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(
        ExerciseCatalog(
            id="0025", name="barbell bench press", category="chest", body_part="chest",
            equipment="barbell", target="pectorals", muscle_group="chest",
            secondary_muscles=[], instructions_en="", instruction_steps_en=[],
            image="", gif_url="", attribution="",
        )
    )
    # Mirrors the 0003 seed; the test DB is built by create_all, not Alembic.
    session.add(
        Course(
            slug="linear-3x", name="Linear 3-day", weeks=2, days_per_week=3,
            weekly_load_step_kg=2.5, session_names=["Push A", "Pull A", "Legs A"],
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "g@test.com", "password": "password1", "display_name": "G"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ── N1 ───────────────────────────────────────────────────────────────

def test_n1_portion_round_trips(client, auth):
    r = client.post(
        "/api/nutrition/log",
        json={"food_name": "oats", "calories": 150, "quantity": 40, "unit": "g"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["quantity"] == 40
    assert r.json()["unit"] == "g"

    day = client.get("/api/nutrition/daily", headers=auth).json()
    assert day["foods"][0]["quantity"] == 40


def test_n1_portion_is_optional_for_pre_n1_clients(client, auth):
    r = client.post("/api/nutrition/log", json={"food_name": "x", "calories": 1}, headers=auth)
    assert r.status_code == 200
    assert r.json()["quantity"] is None
    assert r.json()["unit"] == ""


# ── N2 ───────────────────────────────────────────────────────────────

def test_n2_water_appends_and_daily_sums_against_a_weight_goal(client, auth):
    client.put("/api/profile", json={"weight_kg": 80}, headers=auth)
    for ml in (250, 250, 500):
        assert client.post("/api/nutrition/water", json={"ml": ml}, headers=auth).status_code == 200

    day = client.get("/api/nutrition/daily", headers=auth).json()
    assert day["water_ml"] == 1000
    assert day["water_goal_ml"] == 80 * 35


def test_n2_water_rejects_nonsense(client, auth):
    assert client.post("/api/nutrition/water", json={"ml": 0}, headers=auth).status_code == 422
    assert client.post("/api/nutrition/water", json={"ml": 9000}, headers=auth).status_code == 422


# ── N3 ───────────────────────────────────────────────────────────────

def test_n3_weight_change_records_a_weigh_in(client, auth, db):
    client.put("/api/profile", json={"weight_kg": 80}, headers=auth)
    client.put("/api/profile", json={"weight_kg": 79.5}, headers=auth)
    hist = client.get("/api/profile/weigh-ins", headers=auth).json()
    assert [h["weight_kg"] for h in hist] == [79.5, 80]  # newest first


def test_n3_resaving_the_same_weight_does_not_fabricate_a_point(client, auth, db):
    client.put("/api/profile", json={"weight_kg": 80}, headers=auth)
    client.put("/api/profile", json={"weight_kg": 80, "age": 30}, headers=auth)
    assert db.query(WeighIn).count() == 1


# ── N4 ───────────────────────────────────────────────────────────────

def test_n4_enrol_then_each_workout_advances_the_cursor(client, auth):
    course_id = client.get("/api/courses", headers=auth).json()[0]["id"]
    e = client.post("/api/courses/enrol", json={"course_id": course_id}, headers=auth).json()
    assert (e["current_week"], e["current_day"], e["session_name"]) == (1, 1, "Push A")
    assert e["sessions_total"] == 6

    sets = [{"exercise_id": "0025", "weight_kg": 60, "reps": 5}]
    client.post("/api/workouts", json={"sets": sets}, headers=auth)
    e = client.get("/api/courses/current", headers=auth).json()
    assert (e["current_week"], e["current_day"], e["session_name"]) == (1, 2, "Pull A")
    assert e["sessions_done"] == 1

    # Roll the week.
    client.post("/api/workouts", json={"sets": sets}, headers=auth)
    client.post("/api/workouts", json={"sets": sets}, headers=auth)
    e = client.get("/api/courses/current", headers=auth).json()
    assert (e["current_week"], e["current_day"]) == (2, 1)


def test_n4_finishing_the_last_session_completes_the_course(client, auth):
    course_id = client.get("/api/courses", headers=auth).json()[0]["id"]
    client.post("/api/courses/enrol", json={"course_id": course_id}, headers=auth)
    sets = [{"exercise_id": "0025", "weight_kg": 60, "reps": 5}]
    for _ in range(6):
        client.post("/api/workouts", json={"sets": sets}, headers=auth)

    assert client.get("/api/courses/current", headers=auth).json() is None
    # A seventh workout must not crash or resurrect it.
    assert client.post("/api/workouts", json={"sets": sets}, headers=auth).status_code == 200


def test_n4_enrolling_again_abandons_the_old_course(client, auth, db):
    course_id = client.get("/api/courses", headers=auth).json()[0]["id"]
    first = client.post("/api/courses/enrol", json={"course_id": course_id}, headers=auth).json()
    second = client.post("/api/courses/enrol", json={"course_id": course_id}, headers=auth).json()
    assert second["id"] != first["id"]
    assert client.get("/api/courses/current", headers=auth).json()["id"] == second["id"]


# ── N5 ───────────────────────────────────────────────────────────────
# Barcode lookup now goes through services/food_sources (Open Food Facts, then
# USDA Branded); its behaviour is covered in test_food_sources.py. Here: the
# endpoint contract.

def test_n5_bad_barcode_is_rejected_before_the_network(client, auth, monkeypatch):
    called = []
    async def spy(code):
        called.append(code)
        return None, []
    monkeypatch.setattr("app.services.food_sources.lookup_barcode", spy)
    assert client.get("/api/nutrition/barcode/123", headers=auth).status_code == 400
    assert not called


def test_n5_unknown_barcode_is_404_not_502(client, auth, monkeypatch):
    async def none(code):
        return None, []
    monkeypatch.setattr("app.services.food_sources.lookup_barcode", none)
    assert client.get("/api/nutrition/barcode/12345678", headers=auth).status_code == 404


# ── R1 ───────────────────────────────────────────────────────────────

def test_r1_prescription_persists_on_the_routine(client, auth):
    r = client.post(
        "/api/routines",
        json={"name": "Push", "exercises": [
            {"exercise_id": "0025", "default_sets": 4, "target_weight_kg": 62.5, "target_reps": 8},
        ]},
        headers=auth,
    )
    assert r.status_code == 200
    ex = r.json()["exercises"][0]
    assert ex["target_weight_kg"] == 62.5 and ex["target_reps"] == 8

    listed = client.get("/api/routines", headers=auth).json()[0]["exercises"][0]
    assert listed["target_weight_kg"] == 62.5


def test_r1_no_target_is_null_not_zero(client, auth):
    r = client.post(
        "/api/routines",
        json={"name": "BW", "exercises": [{"exercise_id": "0025"}]},
        headers=auth,
    )
    ex = r.json()["exercises"][0]
    assert ex["target_weight_kg"] is None and ex["target_reps"] is None


# ── W1 ───────────────────────────────────────────────────────────────

def test_w1_same_client_id_returns_the_same_workout(client, auth, db):
    body = {"client_id": "abc-123", "sets": [{"exercise_id": "0025", "weight_kg": 60, "reps": 5}]}
    a = client.post("/api/workouts", json=body, headers=auth).json()
    b = client.post("/api/workouts", json=body, headers=auth).json()
    assert a["id"] == b["id"]
    assert db.query(WorkoutSession).count() == 1


def test_w1_replay_does_not_re_award_records(client, auth):
    body = {"client_id": "pr-1", "sets": [{"exercise_id": "0025", "weight_kg": 100, "reps": 1}]}
    first = client.post("/api/workouts", json=body, headers=auth).json()
    assert first["sets"][0]["is_pr"] is True
    replay = client.post("/api/workouts", json=body, headers=auth).json()
    # The record is still marked on the set, but new_achievements is not
    # re-announced — the slab would otherwise fire twice.
    assert replay["sets"][0]["is_pr"] is True
    assert replay["new_achievements"] == []


def test_w1_client_id_is_scoped_per_user(client, db):
    def register(email):
        r = client.post("/api/auth/register",
                        json={"email": email, "password": "password1", "display_name": "x"})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    u1, u2 = register("u1@test.com"), register("u2@test.com")
    body = {"client_id": "shared", "sets": [{"exercise_id": "0025", "weight_kg": 1, "reps": 1}]}
    a = client.post("/api/workouts", json=body, headers=u1).json()
    b = client.post("/api/workouts", json=body, headers=u2).json()
    assert a["id"] != b["id"]


def test_w1_omitting_client_id_still_inserts_every_time(client, auth, db):
    body = {"sets": [{"exercise_id": "0025", "weight_kg": 60, "reps": 5}]}
    client.post("/api/workouts", json=body, headers=auth)
    client.post("/api/workouts", json=body, headers=auth)
    assert db.query(WorkoutSession).count() == 2
