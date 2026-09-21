"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-24

The schema as it stood when Alembic was wired in: twelve tables, hand-written.

History of this file, because it matters: it began as a no-op stub relying on
Base.metadata.create_all() at startup. PR4 removed that call, and the first
replacement built this baseline from Base.metadata at runtime — which meant it
drifted *with* the models. Once 0003 added columns to food_logs, a fresh
install would have created them here and then failed adding them again in
0003. A baseline must be frozen text, not a reference to a moving target.

Existing databases created under the old startup path have no alembic_version
row. Stamp them once, then migrate normally:

    alembic stamp 0001
    alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("height_cm", sa.Float(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("daily_calorie_goal", sa.Integer(), nullable=True),
        sa.Column("rest_seconds", sa.Integer(), nullable=True),
    )

    op.create_table(
        "exercises",
        sa.Column("id", sa.String(length=8), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("body_part", sa.String(length=64), nullable=True),
        sa.Column("equipment", sa.String(length=64), nullable=True),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column("muscle_group", sa.String(length=128), nullable=True),
        sa.Column("secondary_muscles", sa.JSON(), nullable=True),
        sa.Column("instructions_en", sa.Text(), nullable=True),
        sa.Column("instruction_steps_en", sa.JSON(), nullable=True),
        sa.Column("image", sa.String(length=255), nullable=True),
        sa.Column("gif_url", sa.String(length=255), nullable=True),
        sa.Column("attribution", sa.String(length=255), nullable=True),
    )
    for col in ("name", "category", "body_part", "equipment", "target"):
        op.create_index(f"ix_exercises_{col}", "exercises", [col])

    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_volume", sa.Float(), nullable=True),
        sa.Column("calories_burned", sa.Float(), nullable=True),
        sa.Column("source_query", sa.Text(), nullable=True),
    )
    op.create_index("ix_workout_sessions_user_id", "workout_sessions", ["user_id"])

    op.create_table(
        "workout_sets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("workout_sessions.id"), nullable=False),
        sa.Column("exercise_id", sa.String(length=8), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=True),
        sa.Column("set_number", sa.Integer(), nullable=True),
        sa.Column("volume", sa.Float(), nullable=True),
        sa.Column("is_pr", sa.Boolean(), nullable=True),
        sa.Column("pr_types", sa.JSON(), nullable=True),
    )
    op.create_index("ix_workout_sets_session_id", "workout_sets", ["session_id"])
    op.create_index("ix_workout_sets_exercise_id", "workout_sets", ["exercise_id"])

    op.create_table(
        "food_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("logged_at", sa.DateTime(), nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("food_name", sa.String(length=255), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("protein", sa.Float(), nullable=True),
        sa.Column("carbs", sa.Float(), nullable=True),
        sa.Column("fat", sa.Float(), nullable=True),
        sa.Column("meal_type", sa.String(length=32), nullable=True),
        sa.Column("source_confidence", sa.Float(), nullable=True),
    )
    op.create_index("ix_food_logs_user_id", "food_logs", ["user_id"])

    op.create_table(
        "personal_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("exercise_id", sa.String(length=8), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("achieved_at", sa.DateTime(), nullable=True),
        sa.Column("workout_set_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_personal_records_user_id", "personal_records", ["user_id"])
    op.create_index("ix_personal_records_exercise_id", "personal_records", ["exercise_id"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("icon_key", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("earned_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_achievements_user_id", "achievements", ["user_id"])

    op.create_table(
        "challenge_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=True),
        sa.Column("target_volume", sa.Float(), nullable=True),
        sa.Column("current_volume", sa.Float(), nullable=True),
    )
    op.create_index("ix_challenge_progress_user_id", "challenge_progress", ["user_id"])

    op.create_table(
        "routines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_routines_user_id", "routines", ["user_id"])

    op.create_table(
        "routine_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("routine_id", sa.Integer(), sa.ForeignKey("routines.id"), nullable=False),
        sa.Column("exercise_id", sa.String(length=8), sa.ForeignKey("exercises.id"), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("default_sets", sa.Integer(), nullable=True),
    )
    op.create_index("ix_routine_exercises_routine_id", "routine_exercises", ["routine_id"])
    op.create_index("ix_routine_exercises_exercise_id", "routine_exercises", ["exercise_id"])


def downgrade() -> None:
    for table in (
        "routine_exercises",
        "routines",
        "challenge_progress",
        "achievements",
        "personal_records",
        "food_logs",
        "workout_sets",
        "workout_sessions",
        "exercises",
        "profiles",
        "password_reset_tokens",
        "users",
    ):
        op.drop_table(table)
