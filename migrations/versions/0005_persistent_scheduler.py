"""Persistent publication and comment scheduler.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from facebook_content_publisher.infrastructure.database.orm import UTCDateTime

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _add_missing(table: str, definitions: dict[str, sa.Column]) -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for name, column in definitions.items():
            if name not in existing:
                batch.add_column(column)


def upgrade() -> None:
    _add_missing(
        "publications",
        {
            "started_at_utc": sa.Column("started_at_utc", UTCDateTime()),
            "completed_at_utc": sa.Column("completed_at_utc", UTCDateTime()),
            "next_retry_at_utc": sa.Column("next_retry_at_utc", UTCDateTime()),
            "lease_owner": sa.Column("lease_owner", sa.String(100)),
            "lease_expires_at_utc": sa.Column("lease_expires_at_utc", UTCDateTime()),
            "heartbeat_at_utc": sa.Column("heartbeat_at_utc", UTCDateTime()),
            "max_attempts": sa.Column(
                "max_attempts", sa.Integer(), nullable=False, server_default="5"
            ),
            "provider_request_id": sa.Column("provider_request_id", sa.String(100)),
            "cancelled_at_utc": sa.Column("cancelled_at_utc", UTCDateTime()),
            "correlation_id": sa.Column(
                "correlation_id", sa.String(100), nullable=False, server_default=""
            ),
            "post_text_snapshot": sa.Column(
                "post_text_snapshot", sa.Text(), nullable=False, server_default=""
            ),
            "country_code_snapshot": sa.Column(
                "country_code_snapshot", sa.String(10), nullable=False, server_default=""
            ),
            "language_code_snapshot": sa.Column(
                "language_code_snapshot", sa.String(20), nullable=False, server_default=""
            ),
            "comment_text_snapshot": sa.Column(
                "comment_text_snapshot", sa.Text(), nullable=False, server_default=""
            ),
            "link_url_snapshot": sa.Column("link_url_snapshot", sa.Text()),
            "media_snapshot_json": sa.Column(
                "media_snapshot_json", sa.Text(), nullable=False, server_default="[]"
            ),
            "delayed_comment_enabled": sa.Column(
                "delayed_comment_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            "comment_delay_minutes": sa.Column(
                "comment_delay_minutes", sa.Integer(), nullable=False, server_default="330"
            ),
        },
    )
    _add_missing(
        "comment_jobs",
        {
            "started_at_utc": sa.Column("started_at_utc", UTCDateTime()),
            "completed_at_utc": sa.Column("completed_at_utc", UTCDateTime()),
            "lease_owner": sa.Column("lease_owner", sa.String(100)),
            "lease_expires_at_utc": sa.Column("lease_expires_at_utc", UTCDateTime()),
            "heartbeat_at_utc": sa.Column("heartbeat_at_utc", UTCDateTime()),
            "max_attempts": sa.Column(
                "max_attempts", sa.Integer(), nullable=False, server_default="5"
            ),
            "provider_request_id": sa.Column("provider_request_id", sa.String(100)),
            "cancelled_at_utc": sa.Column("cancelled_at_utc", UTCDateTime()),
            "page_id_snapshot": sa.Column(
                "page_id_snapshot", sa.String(100), nullable=False, server_default=""
            ),
            "facebook_post_id_snapshot": sa.Column(
                "facebook_post_id_snapshot", sa.String(100), nullable=False, server_default=""
            ),
            "correlation_id": sa.Column(
                "correlation_id", sa.String(100), nullable=False, server_default=""
            ),
        },
    )
    with op.batch_alter_table("comment_jobs") as batch:
        batch.create_unique_constraint("uq_comment_job_publication", ["publication_id"])
    op.create_index(
        "ix_publication_due", "publications", ["status", "scheduled_at_utc", "next_retry_at_utc"]
    )
    op.create_index(
        "ix_comment_due", "comment_jobs", ["status", "execute_at_utc", "next_retry_at_utc"]
    )


def downgrade() -> None:
    op.drop_index("ix_comment_due", table_name="comment_jobs")
    op.drop_index("ix_publication_due", table_name="publications")
    with op.batch_alter_table("comment_jobs") as batch:
        batch.drop_constraint("uq_comment_job_publication", type_="unique")
        for name in (
            "correlation_id",
            "facebook_post_id_snapshot",
            "page_id_snapshot",
            "cancelled_at_utc",
            "provider_request_id",
            "max_attempts",
            "heartbeat_at_utc",
            "lease_expires_at_utc",
            "lease_owner",
            "completed_at_utc",
            "started_at_utc",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("publications") as batch:
        for name in (
            "comment_delay_minutes",
            "delayed_comment_enabled",
            "media_snapshot_json",
            "link_url_snapshot",
            "comment_text_snapshot",
            "language_code_snapshot",
            "country_code_snapshot",
            "post_text_snapshot",
            "correlation_id",
            "cancelled_at_utc",
            "provider_request_id",
            "max_attempts",
            "heartbeat_at_utc",
            "lease_expires_at_utc",
            "lease_owner",
            "next_retry_at_utc",
            "completed_at_utc",
            "started_at_utc",
        ):
            batch.drop_column(name)
