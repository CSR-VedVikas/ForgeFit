"""N4 — course progression.

An enrolment is a cursor (week, day) over a preset. Finishing a workout
advances it by one day; rolling past days_per_week starts the next week;
rolling past the final week completes the course. Today's kicker and the
session name are read off the cursor, never stored.
"""

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from ..models import Course, CourseEnrolment
from ..schemas import CourseOut, EnrolmentOut


def active_enrolment(db: Session, user_id: int) -> CourseEnrolment | None:
    return (
        db.query(CourseEnrolment)
        .options(joinedload(CourseEnrolment.course))
        .filter(CourseEnrolment.user_id == user_id, CourseEnrolment.completed_at.is_(None))
        .order_by(CourseEnrolment.started_at.desc())
        .first()
    )


def session_name_for(course: Course, day: int) -> str:
    names = course.session_names or []
    if not names:
        return f"Day {day}"
    return names[(day - 1) % len(names)]


def serialize(e: CourseEnrolment) -> EnrolmentOut:
    c = e.course
    total = c.weeks * c.days_per_week
    done = (e.current_week - 1) * c.days_per_week + (e.current_day - 1)
    complete = e.completed_at is not None
    return EnrolmentOut(
        id=e.id,
        course=CourseOut.model_validate(c),
        current_week=e.current_week,
        current_day=e.current_day,
        started_at=e.started_at,
        completed_at=e.completed_at,
        session_name="" if complete else session_name_for(c, e.current_day),
        sessions_done=min(done, total),
        sessions_total=total,
        is_complete=complete,
    )


def advance(db: Session, user_id: int, now: datetime | None = None) -> CourseEnrolment | None:
    """Move the active enrolment forward one session. Called from
    POST /api/workouts after the session is committed. No enrolment, no-op.

    Does not commit — the caller owns the transaction so the advance lands
    with the workout, not before it."""
    e = active_enrolment(db, user_id)
    if not e:
        return None

    e.current_day += 1
    if e.current_day > e.course.days_per_week:
        e.current_day = 1
        e.current_week += 1
    if e.current_week > e.course.weeks:
        e.completed_at = now or datetime.utcnow()
        # Park the cursor on the last real session so sessions_done == total.
        e.current_week = e.course.weeks
        e.current_day = e.course.days_per_week + 1
    return e
