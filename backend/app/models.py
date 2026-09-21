from datetime import datetime, date
from sqlalchemy import (
    String, Float, Integer, Text, DateTime, Date, Boolean, ForeignKey, JSON, UniqueConstraint
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
    water_logs: Mapped[list["WaterLog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    weigh_ins: Mapped[list["WeighIn"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    enrolments: Mapped[list["CourseEnrolment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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
    # W1 — the client picks client_id before it has a network. A retry after
    # a lost response finds the existing row instead of inserting a twin.
    # NULL is distinct in both SQLite and Postgres, so pre-W1 rows coexist.
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_workout_user_client"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # N1 — the portion. nlp_router already parses serving_qty/serving_unit
    # off the provider response; these columns are where it stopped being
    # dropped on save. Nullable because entries logged before N1 have neither.
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="")

    user: Mapped["User"] = relationship(back_populates="food_logs")


class WaterLog(Base):
    """N2 — Fuel's water tile. Goal is 35 ml/kg, computed at read time from
    the profile so a weigh-in moves the target without touching rows here."""

    __tablename__ = "water_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="water_logs")


class WeighIn(Base):
    """N3 — weight history. Profile.weight_kg stays as the current value
    the rest of the app reads; every write to it also appends a row here so
    Fuel's trend and goal-adherence strip have something to draw."""

    __tablename__ = "weigh_ins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="weigh_ins")


class Course(Base):
    """N4 — a training preset with a time dimension, which Routine lacks.

    Presets are seeded by migration 0003 and are not user-editable; an
    enrolment is the user's position in one. weekly_load_step_kg is the
    prescribed increase per week that the session sheet pre-fills."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_load_step_kg: Mapped[float] = mapped_column(Float, default=2.5)
    # Ordered list of session names, one per training day, cycled weekly.
    session_names: Mapped[list] = mapped_column(JSON, default=list)

    enrolments: Mapped[list["CourseEnrolment"]] = relationship(back_populates="course")


class CourseEnrolment(Base):
    __tablename__ = "course_enrolments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="enrolments")
    course: Mapped["Course"] = relationship(back_populates="enrolments")


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
    # R1 — the builder's prescription. Nullable: "no target" is a real state
    # (bodyweight work, or a routine saved before R1) and 0 would lie.
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_reps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise: Mapped["ExerciseCatalog"] = relationship()
