"""Coverage for the PR2/PR5/PR8 work: config guards, refresh rotation and
revocation, and the password-length ceiling."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.main import app
from app.models import RefreshToken

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

GOOD_SECRET = "x" * 48
PROD = {
    "environment": "production",
    "jwt_secret": GOOD_SECRET,
    "database_url": "postgresql://u:p@localhost/forgefit",
    "enable_docs": False,
    "cors_origins": "https://forgefit.example.com",
}


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
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


def register(client, email="t@test.com", password="password1"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": "T"},
    )


# ── PR2: refuse an unsafe production boot ──────────────────────────────

def test_production_accepts_a_sound_config():
    assert Settings(**PROD).is_production


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"jwt_secret": "dev-secret-change-me"}, "placeholder"),
        ({"jwt_secret": "change-me-to-a-long-random-string"}, "placeholder"),
        ({"jwt_secret": "short"}, "32"),
        ({"database_url": "sqlite:///./forgefit.db"}, "SQLite"),
        ({"enable_docs": True}, "ENABLE_DOCS"),
        ({"cors_origins": ""}, "CORS_ORIGINS"),
    ],
)
def test_production_refuses_unsafe_config(override, expected):
    with pytest.raises(ValueError) as exc:
        Settings(**{**PROD, **override})
    assert expected in str(exc.value)


def test_development_tolerates_the_dev_defaults():
    s = Settings(environment="development", jwt_secret="dev-secret-change-me")
    assert not s.is_production


# ── PR3: the LAN CORS regex must not survive into production ───────────

def test_cors_regex_is_dropped_in_production():
    assert Settings(**PROD).effective_cors_origin_regex is None


def test_cors_regex_applies_in_development():
    assert Settings(environment="development").effective_cors_origin_regex


# ── PR5: refresh rotation, reuse detection, real logout ────────────────

def test_login_sets_an_httponly_refresh_cookie(client):
    r = register(client)
    assert r.status_code == 200
    cookie = r.cookies.get("forgefit_refresh")
    assert cookie
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/auth" in set_cookie


def test_refresh_returns_a_new_access_token(client):
    register(client)
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert r.json()["access_token"]
    me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {r.json()['access_token']}"},
    )
    assert me.status_code == 200


def test_refresh_without_a_cookie_is_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_rotates_the_stored_token(client, db):
    register(client)
    first = db.query(RefreshToken).one()
    client.post("/api/auth/refresh")
    db.expire_all()
    rows = db.query(RefreshToken).order_by(RefreshToken.id).all()
    assert len(rows) == 2
    assert rows[0].id == first.id and rows[0].revoked is True
    assert rows[1].revoked is False


def test_replaying_a_rotated_token_kills_every_session(client, db):
    register(client)
    stolen = client.cookies.get("forgefit_refresh")
    client.post("/api/auth/refresh")  # rotates; `stolen` is now revoked

    client.cookies.set("forgefit_refresh", stolen)
    replay = client.post("/api/auth/refresh")
    assert replay.status_code == 401

    db.expire_all()
    assert all(r.revoked for r in db.query(RefreshToken).all())


def test_logout_revokes_rather_than_just_forgetting(client, db):
    register(client)
    assert client.post("/api/auth/logout").status_code == 200
    db.expire_all()
    assert all(r.revoked for r in db.query(RefreshToken).all())


def test_a_refresh_token_cannot_authenticate_an_api_call(client):
    register(client)
    raw = client.cookies.get("forgefit_refresh")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


def test_password_change_signs_other_devices_out(client, db):
    register(client)
    token = client.post("/api/auth/refresh").json()["access_token"]
    before = {r.id for r in db.query(RefreshToken).filter_by(revoked=False).all()}

    r = client.put(
        "/api/auth/password",
        json={"current_password": "password1", "new_password": "password2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    db.expire_all()
    live = {r.id for r in db.query(RefreshToken).filter_by(revoked=False).all()}
    assert live and not (live & before)  # replaced, not merely added to


# ── PR8: no silent password truncation ─────────────────────────────────

def test_over_length_password_is_rejected_not_truncated(client):
    r = register(client, email="long@test.com", password="p" * 100)
    assert r.status_code == 422  # schema ceiling


def test_a_72_byte_password_still_works(client):
    r = register(client, email="edge@test.com", password="p" * 72)
    assert r.status_code == 200


def test_prefix_of_a_long_password_is_not_accepted(client):
    register(client, email="edge2@test.com", password="p" * 72)
    bad = client.post(
        "/api/auth/login/json",
        json={"email": "edge2@test.com", "password": "p" * 71},
    )
    assert bad.status_code == 401
