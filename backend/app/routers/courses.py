from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..db import get_db
from ..models import Course, CourseEnrolment
from ..schemas import CourseOut, EnrolRequest, EnrolmentOut, MessageOut
from ..services import courses as svc

router = APIRouter(prefix="/api/courses", tags=["courses"])


@router.get("", response_model=list[CourseOut])
def list_courses(user: CurrentUser, db: Session = Depends(get_db)):
    return db.query(Course).order_by(Course.days_per_week, Course.weeks).all()


@router.get("/current", response_model=EnrolmentOut | None)
def current(user: CurrentUser, db: Session = Depends(get_db)):
    """The active enrolment, or null. Today reads its kicker and session
    name from this; a null means Today falls back to the routine picker."""
    e = svc.active_enrolment(db, user.id)
    return svc.serialize(e) if e else None


@router.post("/enrol", response_model=EnrolmentOut)
def enrol(payload: EnrolRequest, user: CurrentUser, db: Session = Depends(get_db)):
    course = db.get(Course, payload.course_id)
    if not course:
        raise HTTPException(404, "Course not found")
    # One course at a time. Enrolling again while one is active abandons the
    # old one rather than erroring — the user has already decided.
    for old in (
        db.query(CourseEnrolment)
        .filter(CourseEnrolment.user_id == user.id, CourseEnrolment.completed_at.is_(None))
        .all()
    ):
        old.completed_at = datetime.utcnow()
    e = CourseEnrolment(user_id=user.id, course_id=course.id)
    db.add(e)
    db.commit()
    db.refresh(e)
    return svc.serialize(e)


@router.delete("/current", response_model=MessageOut)
def abandon(user: CurrentUser, db: Session = Depends(get_db)):
    e = svc.active_enrolment(db, user.id)
    if not e:
        raise HTTPException(404, "No active course")
    e.completed_at = datetime.utcnow()
    db.commit()
    return MessageOut(message="Course abandoned.")
