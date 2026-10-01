"""Scheduler hardening and audit metadata.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add(table: str, definitions: dict[str, sa.Column]) -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for name, column in definitions.items():
            if name not in columns:
                batch.add_column(column)


def upgrade() -> None:
    job_fields = {
        "version": sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        "provider_mode_snapshot": sa.Column(
            "provider_mode_snapshot", sa.String(20), nullable=False, server_default="mock"
        ),
        "attention_required": sa.Column(
            "attention_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    }
    _add("publications", job_fields)
    _add(
        "comment_jobs",
        {
            "version": sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            "provider_mode_snapshot": sa.Column(
                "provider_mode_snapshot", sa.String(20), nullable=False, server_default="mock"
            ),
            "attention_required": sa.Column(
                "attention_required", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        },
    )
    _add(
        "activity_logs",
        {
            "correlation_id": sa.Column(
                "correlation_id", sa.String(100), nullable=False, server_default=""
            ),
            "actor": sa.Column("actor", sa.String(20), nullable=False, server_default="system"),
            "metadata_json": sa.Column(
                "metadata_json", sa.Text(), nullable=False, server_default="{}"
            ),
        },
    )
    op.create_index("ix_activity_correlation", "activity_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_activity_correlation", table_name="activity_logs")
    with op.batch_alter_table("activity_logs") as batch:
        for name in ("metadata_json", "actor", "correlation_id"):
            batch.drop_column(name)
    for table in ("comment_jobs", "publications"):
        with op.batch_alter_table(table) as batch:
            for name in ("attention_required", "provider_mode_snapshot", "version"):
                batch.drop_column(name)
