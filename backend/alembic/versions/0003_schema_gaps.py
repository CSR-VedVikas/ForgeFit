"""schema gaps blocking the redesign: N1-N5, R1, W1

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

One migration, because every gap blocks at least one redesigned screen and
the wiring must not start against a half-migrated schema (design/github.md,
"Schema gaps blocking persistence").

  N1  food_logs.quantity / unit         portions were parsed then dropped on save
  N2  water_logs                        Fuel's water tile had nowhere to write
  N3  weigh_ins                         Profile.weight_kg was a single current value
  N4  courses + course_enrolments       Routine has no time dimension
  R1  routine_exercises.target_*        the builder's prescription could not persist
  W1  workout_sessions.client_id        POST /api/workouts had no idempotency key

N5 (barcode lookup) is a service change, not schema; it lands in the same
commit but has no footprint here.

Hand-written rather than --autogenerate: autogenerate against SQLite drops
constraints it cannot express, and the W1 unique constraint is the point.
SQLite needs batch_alter_table for ADD COLUMN with constraints; Postgres
tolerates it, so it is used throughout.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Seeded presets. Names are what Today's kicker and the session sheet show.
COURSE_PRESETS = [
    {
        "slug": "linear-3x",
        "name": "Linear 3-day",
        "description": (
            "Full-body, three days a week, add load every week. The classic "
            "novice progression: if you finished every set, next week is heavier."
        ),
        "weeks": 8,
        "days_per_week": 3,
        "weekly_load_step_kg": 2.5,
        "session_names": ["Push A", "Pull A", "Legs A"],
    },
    {
        "slug": "upper-lower-4x",
        "name": "Upper / Lower 4-day",
        "description": (
            "Two upper, two lower each week. More volume per muscle than "
            "full-body, one more day in the gym."
        ),
        "weeks": 10,
        "days_per_week": 4,
        "weekly_load_step_kg": 2.5,
        "session_names": ["Upper A", "Lower A", "Upper B", "Lower B"],
    },
    {
        "slug": "ppl-6x",
        "name": "Push / Pull / Legs 6-day",
        "description": (
            "Each pattern twice a week. For people who already train most "
            "days and want the split to say so."
        ),
        "weeks": 12,
        "days_per_week": 6,
        "weekly_load_step_kg": 1.25,
        "session_names": ["Push", "Pull", "Legs", "Push", "Pull", "Legs"],
    },
]


def upgrade() -> None:
    # ── N1 ──────────────────────────────────────────────────────────
    with op.batch_alter_table("food_logs") as b:
        b.add_column(sa.Column("quantity", sa.Float(), nullable=True))
        b.add_column(sa.Column("unit", sa.String(length=32), nullable=False, server_default=""))

    # ── N2 ──────────────────────────────────────────────────────────
    op.create_table(
        "water_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("ml", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_water_logs_user_id", "water_logs", ["user_id"])
    op.create_index("ix_water_logs_logged_at", "water_logs", ["logged_at"])

    # ── N3 ──────────────────────────────────────────────────────────
    op.create_table(
        "weigh_ins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("weight_kg", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_weigh_ins_user_id", "weigh_ins", ["user_id"])
    op.create_index("ix_weigh_ins_recorded_at", "weigh_ins", ["recorded_at"])

    # Backfill: every existing profile weight becomes the first weigh-in, so
    # the trend line starts from a real point rather than empty.
    op.execute(
        """
        INSERT INTO weigh_ins (user_id, weight_kg, recorded_at)
        SELECT p.user_id, p.weight_kg, u.created_at
        FROM profiles p JOIN users u ON u.id = p.user_id
        WHERE p.weight_kg IS NOT NULL
        """
    )

    # ── N4 ──────────────────────────────────────────────────────────
    courses = op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("weekly_load_step_kg", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("session_names", sa.JSON(), nullable=True),
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)
    op.bulk_insert(courses, COURSE_PRESETS)

    op.create_table(
        "course_enrolments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("current_week", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_day", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_course_enrolments_user_id", "course_enrolments", ["user_id"])
    op.create_index("ix_course_enrolments_course_id", "course_enrolments", ["course_id"])

    # ── R1 ──────────────────────────────────────────────────────────
    with op.batch_alter_table("routine_exercises") as b:
        b.add_column(sa.Column("target_weight_kg", sa.Float(), nullable=True))
        b.add_column(sa.Column("target_reps", sa.Integer(), nullable=True))

    # ── W1 ──────────────────────────────────────────────────────────
    with op.batch_alter_table("workout_sessions") as b:
        b.add_column(sa.Column("client_id", sa.String(length=64), nullable=True))
        b.create_unique_constraint("uq_workout_user_client", ["user_id", "client_id"])


def downgrade() -> None:
    with op.batch_alter_table("workout_sessions") as b:
        b.drop_constraint("uq_workout_user_client", type_="unique")
        b.drop_column("client_id")

    with op.batch_alter_table("routine_exercises") as b:
        b.drop_column("target_reps")
        b.drop_column("target_weight_kg")

    op.drop_index("ix_course_enrolments_course_id", table_name="course_enrolments")
    op.drop_index("ix_course_enrolments_user_id", table_name="course_enrolments")
    op.drop_table("course_enrolments")
    op.drop_index("ix_courses_slug", table_name="courses")
    op.drop_table("courses")

    op.drop_index("ix_weigh_ins_recorded_at", table_name="weigh_ins")
    op.drop_index("ix_weigh_ins_user_id", table_name="weigh_ins")
    op.drop_table("weigh_ins")

    op.drop_index("ix_water_logs_logged_at", table_name="water_logs")
    op.drop_index("ix_water_logs_user_id", table_name="water_logs")
    op.drop_table("water_logs")

    with op.batch_alter_table("food_logs") as b:
        b.drop_column("unit")
        b.drop_column("quantity")
