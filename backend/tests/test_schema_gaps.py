"""Migration 0003 — one test per gap from design/github.md.

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
from app.services import nutrition_api

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

def test_n5_barcode_returns_a_draftfood_shape(client, auth, monkeypatch):
    async def fake(upc):
        assert upc == "012345678905"
        return {
            "food_name": "Protein bar", "brand": "Acme", "calories": 210,
            "protein": 20, "carbs": 22, "fat": 7, "quantity": 1, "unit": "bar",
        }
    # Patch where the router imported it, not the service module.
    monkeypatch.setattr("app.routers.nutrition.product_by_barcode", fake)

    r = client.get("/api/nutrition/barcode/0-12345-67890-5", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["food_name"] == "Protein bar" and body["upc"] == "012345678905"
    assert body["quantity"] == 1 and body["unit"] == "bar"


def test_n5_unknown_barcode_is_404_not_502(client, auth, monkeypatch):
    async def none(upc):
        return None
    monkeypatch.setattr("app.routers.nutrition.product_by_barcode", none)
    assert client.get("/api/nutrition/barcode/12345678", headers=auth).status_code == 404


def test_n5_bad_barcode_is_rejected_before_the_network(client, auth, monkeypatch):
    called = []
    async def spy(upc):
        called.append(upc)
    monkeypatch.setattr("app.routers.nutrition.product_by_barcode", spy)
    assert client.get("/api/nutrition/barcode/123", headers=auth).status_code == 400
    assert not called


def test_n5_service_maps_provider_fields(monkeypatch):
    import asyncio
    async def fake_get(path, params):
        assert path == "search/item" and params == {"upc": "1"}
        return {"foods": [{
            "food_name": "Milk", "brand_name": "Farm", "nf_calories": 120,
            "nf_protein": 8, "nf_total_carbohydrate": 12, "nf_total_fat": 5,
            "serving_qty": 250, "serving_unit": "ml",
        }]}
    monkeypatch.setattr(nutrition_api, "_get_nutrition", fake_get)
    out = asyncio.run(nutrition_api.product_by_barcode("1"))
    assert out == {
        "food_name": "Milk", "brand": "Farm", "calories": 120.0, "protein": 8.0,
        "carbs": 12.0, "fat": 5.0, "quantity": 250, "unit": "ml",
    }


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
