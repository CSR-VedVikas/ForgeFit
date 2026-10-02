"""food_logs.source / source_ref

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-03

Food data now comes from USDA FoodData Central or Open Food Facts, chosen per
item by the user. Each log records which ("usda" | "off") and the item's id
there: Open Food Facts is ODbL-licensed, so attribution has to know which
entries came from it, and a stored id lets a meal be looked up again.

Existing rows came from the retired provider and get "" for both.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("food_logs") as b:
        b.add_column(sa.Column("source", sa.String(length=16), nullable=False, server_default=""))
        b.add_column(sa.Column("source_ref", sa.String(length=64), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("food_logs") as b:
        b.drop_column("source_ref")
        b.drop_column("source")
