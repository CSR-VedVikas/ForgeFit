from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Profile
from ..schemas import ParseRequest, ParseResponse
from ..auth import CurrentUser
from ..services.nlp_router import parse_user_text
from ..config import get_settings
from ..rate_limit import limiter

router = APIRouter(prefix="/api/nlp", tags=["nlp"])
settings = get_settings()


@router.post("/parse", response_model=ParseResponse)
@limiter.limit(settings.rate_limit_nlp)
async def parse(
    request: Request,
    payload: ParseRequest,
    user: CurrentUser,
    db: Session = Depends(get_db),
):
    text = (payload.text or "").strip()
    if len(text) > settings.max_nlp_chars:
        raise HTTPException(400, f"Input too long (max {settings.max_nlp_chars} characters)")
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    return await parse_user_text(db, text, profile)
