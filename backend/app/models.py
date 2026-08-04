from datetime import datetime, date
from sqlalchemy import (
    String, Float, Integer, Text, DateTime, Date, Boolean, ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)
    workouts: Mapped[list["WorkoutSession"]] = relationship(back_populates="user")
    food_logs: Mapped[list["FoodLog"]] = relationship(back_populates="user")
    personal_records: Mapped[list["PersonalRecord"]] = relationship(back_populates="user")
    achievements: Mapped[list["Achievement"]] = relationship(back_populates="user")
    challenges: Mapped[list["ChallengeProgress"]] = relationship(back_populates="user")
    reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    routines: Mapped[list["Routine"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """PR5 — one row per issued refresh token, so logout can actually revoke.

    The raw token never lands here; only its SHA-256. `jti` is the claim
    carried in the JWT and is what a lookup keys on, which means a stolen
    token can be killed without touching the user's other sessions.
    Rotation: refreshing marks the presented row `revoked` and writes a new
    one, so a replayed token is detectably already-revoked.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_agent: Mapped[str] = mapped_column(String(255), default="")

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="reset_tokens")


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    gender: Mapped[str] = mapped_column(String(20), default="male")
    weight_kg: Mapped[float] = mapped_column(Float, default=75.0)
    height_cm: Mapped[float] = mapped_column(Float, default=175.0)
    age: Mapped[int] = mapped_column(Integer, default=25)
    daily_calorie_goal: Mapped[int] = mapped_column(Integer, default=2200)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=90)

    user: Mapped["User"] = relationship(back_populates="profile")


class ExerciseCatalog(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    body_part: Mapped[str] = mapped_column(String(64), index=True)
    equipment: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(128), index=True)
    muscle_group: Mapped[str] = mapped_column(String(128), default="")
    secondary_muscles: Mapped[list] = mapped_column(JSON, default=list)
    instructions_en: Mapped[str] = mapped_column(Text, default="")
    instruction_steps_en: Mapped[list] = mapped_column(JSON, default=list)
    image: Mapped[str] = mapped_column(String(255), default="")
    gif_url: Mapped[str] = mapped_column(String(255), default="")
    attribution: Mapped[str] = mapped_column(String(255), default="")


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    total_volume: Mapped[float] = mapped_column(Float, default=0.0)
    calories_burned: Mapped[float] = mapped_column(Float, default=0.0)
    source_query: Mapped[str] = mapped_column(Text, default="")

    user: Mapped["User"] = relationship(back_populates="workouts")
    sets: Mapped[list["WorkoutSet"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class WorkoutSet(Base):
    __tablename__ = "workout_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("workout_sessions.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    set_number: Mapped[int] = mapped_column(Integer, default=1)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    is_pr: Mapped[bool] = mapped_column(Boolean, default=False)
    pr_types: Mapped[list] = mapped_column(JSON, default=list)

    session: Mapped["WorkoutSession"] = relationship(back_populates="sets")
    exercise: Mapped["ExerciseCatalog"] = relationship()


class FoodLog(Base):
    __tablename__ = "food_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    query_text: Mapped[str] = mapped_column(Text, default="")
    food_name: Mapped[str] = mapped_column(String(255), default="")
    calories: Mapped[float] = mapped_column(Float, default=0.0)
    protein: Mapped[float] = mapped_column(Float, default=0.0)
    carbs: Mapped[float] = mapped_column(Float, default=0.0)
    fat: Mapped[float] = mapped_column(Float, default=0.0)
    meal_type: Mapped[str] = mapped_column(String(32), default="snack")
    source_confidence: Mapped[float] = mapped_column(Float, default=1.0)

    user: Mapped["User"] = relationship(back_populates="food_logs")


class PersonalRecord(Base):
    __tablename__ = "personal_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(32))  # max_weight | max_volume | max_reps
    value: Mapped[float] = mapped_column(Float, default=0.0)
    achieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workout_set_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship(back_populates="personal_records")
    exercise: Mapped["ExerciseCatalog"] = relationship()


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    icon_key: Mapped[str] = mapped_column(String(64), default="trophy")
    title: Mapped[str] = mapped_column(String(255))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    user: Mapped["User"] = relationship(back_populates="achievements")


class ChallengeProgress(Base):
    __tablename__ = "challenge_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    week_start: Mapped[date] = mapped_column(Date)
    target_volume: Mapped[float] = mapped_column(Float, default=0.0)
    current_volume: Mapped[float] = mapped_column(Float, default=0.0)

    user: Mapped["User"] = relationship(back_populates="challenges")


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="routines")
    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="RoutineExercise.sort_order"
    )


class RoutineExercise(Base):
    __tablename__ = "routine_exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id"), index=True)
    exercise_id: Mapped[str] = mapped_column(ForeignKey("exercises.id"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_sets: Mapped[int] = mapped_column(Integer, default=3)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise: Mapped["ExerciseCatalog"] = relationship()
