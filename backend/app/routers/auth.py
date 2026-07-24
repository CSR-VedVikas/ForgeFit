import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, Profile, PasswordResetToken
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
from ..auth import hash_password, verify_password, create_access_token, CurrentUser
from ..config import get_settings
from ..rate_limit import limiter
from ..logging_config import logger

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
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
    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/login/json", response_model=TokenOut)
@limiter.limit(settings.rate_limit_auth)
def login_json(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return TokenOut(access_token=create_access_token(str(user.id)))


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
        expires_at=datetime.utcnow() + timedelta(hours=1),
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
def reset_password(request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    th = _hash_token(payload.token)
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == th, PasswordResetToken.used.is_(False))
        .first()
    )
    if not row or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "Invalid or expired reset token")

    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(400, "Invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    row.used = True
    db.commit()
    return MessageOut(message="Password updated. You can sign in now.")


@router.put("/password", response_model=MessageOut)
@limiter.limit(settings.rate_limit_auth)
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    db_user = db.get(User, user.id)
    if not db_user or not verify_password(payload.current_password, db_user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    db_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return MessageOut(message="Password changed.")


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
