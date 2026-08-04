"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-24

This revision used to be a no-op stub, on the assumption that
Base.metadata.create_all() in app startup would build the schema and Alembic
only had to record a baseline. PR4 removed that call, which left `alembic
upgrade head` creating nothing at all on a fresh install.

The baseline is now real. It builds from Base.metadata rather than a
hand-written table list so it cannot drift from the models, and because
create_all skips tables that already exist, running it against a database
built the old way is a no-op.

Existing databases created under the old startup path have no alembic_version
row. Stamp them once, then migrate normally:

    alembic stamp 0001
    alembic upgrade head
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.db import Base
    from app import models  # noqa: F401  — registers every mapper on Base

    # refresh_tokens belongs to 0002; excluded so this revision reproduces the
    # schema as it stood at the baseline.
    tables = [t for name, t in Base.metadata.tables.items() if name != "refresh_tokens"]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)


def downgrade() -> None:
    from app.db import Base
    from app import models  # noqa: F401

    tables = [t for name, t in Base.metadata.tables.items() if name != "refresh_tokens"]
    Base.metadata.drop_all(bind=op.get_bind(), tables=tables)
