import hashlib
import secrets
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, Profile, PasswordResetToken, RefreshToken
from ..schemas import (
    UserRegister,
    UserLogin,
    TokenOut,
    UserOut,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ChangePasswordRequest,
    ChangeEmailRequest,
    MessageOut,
)
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    issue_refresh_token,
    hash_refresh_token,
    decode_token,
    revoke_all_for_user,
    password_too_long,
    utcnow,
    CurrentUser,
)
from ..config import get_settings
from ..rate_limit import limiter
from ..logging_config import logger

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _reject_long_password(password: str) -> None:
    """PR8 — an over-length password is refused at the door rather than
    silently cut down to its first 72 bytes."""
    if password_too_long(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at most 72 bytes. Longer passphrases "
            "cannot be hashed without silently discarding the remainder.",
        )


def _set_refresh_cookie(response: Response, raw: str) -> None:
    """PR5 — httpOnly so no script on the page can read it, Secure in
    production, and scoped to /api/auth so it is not attached to every
    ordinary API call."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw,
        max_age=settings.refresh_token_expire_minutes * 60,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        domain=settings.refresh_cookie_domain or None,
    )


def _issue_session(
    db: Session, response: Response, user_id: int, user_agent: str
) -> TokenOut:
    raw, _row = issue_refresh_token(db, user_id, user_agent)
    db.commit()
    _set_refresh_cookie(response, raw)
    return TokenOut(access_token=create_access_token(str(user_id)))


@router.post("/register", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def register(
    request: Request,
    payload: UserRegister,
    response: Response,
    db: Session = Depends(get_db),
):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    _reject_long_password(payload.password)
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()
    db.add(
        Profile(
            user_id=user.id,
            display_name=payload.display_name or payload.email.split("@")[0],
        )
    )
    db.commit()
    return _issue_session(db, response, user.id, request.headers.get("user-agent", ""))


@router.post("/login", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return _issue_session(db, response, user.id, request.headers.get("user-agent", ""))


@router.post("/login/json", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def login_json(
    request: Request,
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return _issue_session(db, response, user.id, request.headers.get("user-agent", ""))


@router.post("/refresh", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    forgefit_refresh: str | None = Cookie(default=None, alias="forgefit_refresh"),
):
    """PR5 — exchange the httpOnly refresh cookie for a new access token.

    Rotates on every call: the presented token is revoked and a fresh one
    issued. Replaying an already-revoked token is treated as theft and every
    session for that user is killed, because the legitimate holder and the
    attacker cannot be told apart at this point.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired. Sign in again.",
    )
    if not forgefit_refresh:
        raise unauthorized

    try:
        payload = decode_token(forgefit_refresh, "refresh")
        user_id = int(payload["sub"])
        jti = payload["jti"]
    except (JWTError, KeyError, ValueError, TypeError):
        _clear_refresh_cookie(response)
        raise unauthorized

    row = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
    if not row or row.token_hash != hash_refresh_token(forgefit_refresh):
        _clear_refresh_cookie(response)
        raise unauthorized

    if row.revoked:
        # Reuse of a rotated token. Assume compromise and end every session.
        revoked = revoke_all_for_user(db, row.user_id)
        db.commit()
        logger.warning(
            '"refresh_reuse":"detected","user_id":%s,"sessions_revoked":%s',
            row.user_id,
            revoked,
        )
        _clear_refresh_cookie(response)
        raise unauthorized

    if row.expires_at < utcnow().replace(tzinfo=None):
        _clear_refresh_cookie(response)
        raise unauthorized

    user = db.get(User, user_id)
    if not user:
        _clear_refresh_cookie(response)
        raise unauthorized

    row.revoked = True
    return _issue_session(db, response, user.id, request.headers.get("user-agent", ""))


@router.post("/logout", response_model=MessageOut)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    forgefit_refresh: str | None = Cookie(default=None, alias="forgefit_refresh"),
):
    """PR5 — logout now actually revokes. Previously it was client-side only,
    so a token copied off the device stayed valid for its full lifetime.

    Unauthenticated on purpose: signing out must work even when the access
    token has already expired.
    """
    if forgefit_refresh:
        try:
            payload = decode_token(forgefit_refresh, "refresh")
            jti = payload.get("jti")
            if jti:
                db.query(RefreshToken).filter(
                    RefreshToken.jti == jti, RefreshToken.revoked.is_(False)
                ).update({"revoked": True})
                db.commit()
        except JWTError:
            pass  # An unreadable cookie is cleared below regardless.
    _clear_refresh_cookie(response)
    return MessageOut(message="Signed out.")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    name = user.profile.display_name if user.profile else ""
    return UserOut(id=user.id, email=user.email, display_name=name)


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
@limiter.limit(settings.rate_limit_auth)
def forgot_password(request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always return a generic message to avoid email enumeration."""
    generic = "If that email is registered, a reset link is ready."
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user:
        return ForgotPasswordResponse(message=generic)

    # Invalidate prior unused tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update({"used": True})

    raw = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=(utcnow() + timedelta(hours=1)).replace(tzinfo=None),
        used=False,
    )
    db.add(row)
    db.commit()

    reset_path = f"/reset-password?token={raw}"
    logger.info('"password_reset":"issued","user_id":%s', user.id)

    # Dev/local: no SMTP yet — return token so you can test recovery in the UI
    if not settings.is_production:
        return ForgotPasswordResponse(
            message=generic + " (Dev mode: use the token below.)",
            reset_token=raw,
            reset_path=reset_path,
        )

    # Production: wire SMTP/SendGrid here later; never return raw token
    return ForgotPasswordResponse(message=generic)


@router.post("/reset-password", response_model=MessageOut)
@limiter.limit(settings.rate_limit_auth)
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    _reject_long_password(payload.new_password)
    th = _hash_token(payload.token)
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == th, PasswordResetToken.used.is_(False))
        .first()
    )
    if not row or row.expires_at < utcnow().replace(tzinfo=None):
        raise HTTPException(400, "Invalid or expired reset token")

    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(400, "Invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    row.used = True
    # A recovered account must not leave the attacker's sessions alive.
    revoked = revoke_all_for_user(db, user.id)
    db.commit()
    _clear_refresh_cookie(response)
    logger.info('"password_reset":"completed","user_id":%s,"sessions_revoked":%s', user.id, revoked)
    return MessageOut(message="Password updated. You can sign in now.")


@router.put("/password", response_model=MessageOut)
@limiter.limit(settings.rate_limit_auth)
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: CurrentUser,
    response: Response,
    db: Session = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    _reject_long_password(payload.new_password)
    db_user = db.get(User, user.id)
    if not db_user or not verify_password(payload.current_password, db_user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    db_user.password_hash = hash_password(payload.new_password)
    revoke_all_for_user(db, db_user.id)
    db.commit()
    # The caller keeps working: a fresh session replaces the ones just killed.
    raw, _row = issue_refresh_token(db, db_user.id, request.headers.get("user-agent", ""))
    db.commit()
    _set_refresh_cookie(response, raw)
    return MessageOut(message="Password changed. Other devices were signed out.")


@router.put("/email", response_model=UserOut)
@limiter.limit(settings.rate_limit_auth)
def change_email(
    request: Request,
    payload: ChangeEmailRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    db_user = db.get(User, user.id)
    if not db_user or not verify_password(payload.password, db_user.password_hash):
        raise HTTPException(400, "Password is incorrect")
    new_email = payload.new_email.lower()
    taken = db.query(User).filter(User.email == new_email, User.id != user.id).first()
    if taken:
        raise HTTPException(400, "Email already in use")
    db_user.email = new_email
    db.commit()
    db.refresh(db_user)
    name = db_user.profile.display_name if db_user.profile else ""
    return UserOut(id=db_user.id, email=db_user.email, display_name=name)
