import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ExerciseCatalog
from app.services.pr_engine import apply_prs_and_achievements, effective_weight
from app.models import User, Profile, WorkoutSession, WorkoutSet
from app.services import openai_nlp


SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    session.add(
        ExerciseCatalog(
            id="0025",
            name="barbell bench press",
            category="chest",
            body_part="chest",
            equipment="barbell",
            target="pectorals",
            muscle_group="chest",
            secondary_muscles=[],
            instructions_en="press",
            instruction_steps_en=["press"],
            image="images/0025.jpg",
            gif_url="videos/0025.gif",
            attribution="test",
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
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "a@test.com", "password": "password1", "display_name": "A"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@test.com"

    bad = client.post("/api/auth/login/json", json={"email": "a@test.com", "password": "wrongpass"})
    assert bad.status_code == 401


def test_workout_requires_auth(client):
    r = client.get("/api/workouts")
    assert r.status_code == 401


def test_create_workout_and_pr(client, db):
    reg = client.post(
        "/api/auth/register",
        json={"email": "b@test.com", "password": "password1", "display_name": "B"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post(
        "/api/workouts",
        headers=headers,
        json={
            "notes": "t",
            "sets": [
                {"exercise_id": "0025", "weight_kg": 60, "reps": 8, "set_number": 1},
                {"exercise_id": "0025", "weight_kg": 70, "reps": 5, "set_number": 2},
            ],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_volume"] == 60 * 8 + 70 * 5
    assert any(s["is_pr"] for s in data["sets"])
    assert len(data["new_achievements"]) >= 1


def test_heuristic_strength_parse():
    parsed = openai_nlp._heuristic_strength("bench press 3x8 at 60kg")
    assert parsed["sets"]
    assert parsed["sets"][0]["reps"] == 8
    assert parsed["sets"][0]["sets_count"] == 3
    assert parsed["sets"][0]["weight_kg"] == 60


def test_effective_weight_bodyweight(db):
    user = User(email="c@test.com", password_hash="x")
    db.add(user)
    db.flush()
    profile = Profile(user_id=user.id, weight_kg=80)
    ex = db.get(ExerciseCatalog, "0025")
    ex.equipment = "body weight"
    db.add(profile)
    db.commit()
    assert effective_weight(0, profile, ex) == 80
