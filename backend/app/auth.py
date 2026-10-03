import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
# python-jose was replaced: it carried three advisories (one unfixed) and pulled
# in ecdsa, which has its own. PyJWT is maintained and does exactly HS256.
from jwt import PyJWTError as JWTError
import bcrypt
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User, RefreshToken

# bcrypt directly. passlib wrapped it until Oct 2026; it has not been released
# since 2020 and no longer reads current bcrypt's version. Hashes are the same
# $2b$ format at cost 12, so every existing password still verifies.
BCRYPT_ROUNDS = 12
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
settings = get_settings()

# bcrypt hashes at most 72 bytes and silently ignores the rest.
BCRYPT_MAX_BYTES = 72


def utcnow() -> datetime:
    """PR9 — timezone-aware. datetime.utcnow() is deprecated in 3.12 and
    returns a naive value that compares wrongly against anything aware."""
    return datetime.now(timezone.utc)


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > BCRYPT_MAX_BYTES


def hash_password(password: str) -> str:
    """PR8 — refuse rather than truncate.

    The old behaviour hashed password[:72], so a 100-character passphrase was
    authenticated on its first 72 characters and any passphrase sharing that
    prefix also worked. Callers must reject over-length input before reaching
    here; this raise is the backstop.
    """
    if password_too_long(password):
        raise ValueError(
            f"Password exceeds {BCRYPT_MAX_BYTES} bytes and cannot be hashed "
            "without silent truncation."
        )
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(BCRYPT_ROUNDS)).decode("ascii")


def _checkpw(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:BCRYPT_MAX_BYTES], hashed.encode("ascii"))
    except ValueError:  # a malformed stored hash is a failed login, not a 500
        return False


def verify_password(plain: str, hashed: str) -> bool:
    """Deliberately still truncates.

    Accounts created before PR8 have a hash of their first 72 bytes. Verifying
    the full string would lock those users out of their own accounts. New
    passwords can no longer exceed 72 bytes, so this path narrows over time
    and never widens.
    """
    return _checkpw(plain, hashed)


# A real bcrypt hash of a throwaway value. Login checks a password against it
# when the email is unknown, so "no such account" costs the same ~bcrypt time
# as "wrong password" and response timing does not reveal which emails exist.
_TIMING_DUMMY_HASH = bcrypt.hashpw(b"forgefit-timing-equaliser", bcrypt.gensalt(BCRYPT_ROUNDS)).decode("ascii")


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        _checkpw(password, _TIMING_DUMMY_HASH)
        return None
    return user if verify_password(password, user.password_hash) else None


def _encode(claims: dict, expires_delta: timedelta) -> str:
    payload = {**claims, "iat": utcnow(), "exp": utcnow() + expires_delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    return _encode(
        {"sub": subject, "type": "access"},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Returns (raw_token, jti, expires_at).

    The raw token goes into an httpOnly cookie and is never persisted; only
    its SHA-256 is stored, so a database leak does not yield usable sessions.
    """
    jti = secrets.token_urlsafe(24)
    expires_at = utcnow() + timedelta(minutes=settings.refresh_token_expire_minutes)
    raw = _encode(
        {"sub": subject, "type": "refresh", "jti": jti},
        timedelta(minutes=settings.refresh_token_expire_minutes),
    )
    return raw, jti, expires_at


def issue_refresh_token(
    db: Session, user_id: int, user_agent: str = ""
) -> tuple[str, RefreshToken]:
    raw, jti, expires_at = create_refresh_token(str(user_id))
    row = RefreshToken(
        user_id=user_id,
        jti=jti,
        token_hash=hash_refresh_token(raw),
        expires_at=expires_at.replace(tzinfo=None),
        revoked=False,
        user_agent=(user_agent or "")[:255],
    )
    db.add(row)
    return raw, row


def revoke_all_for_user(db: Session, user_id: int) -> int:
    """Used on password change and password reset — a credential change must
    end every session, not just the one that made it."""
    return (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .update({"revoked": True})
    )


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected a {expected_type} token")
    return payload


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # expected_type pins this to access tokens: a refresh token lifted from
        # the cookie must not authenticate an API call.
        payload = decode_token(token, "access")
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    if not user:
        raise credentials_exception
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
