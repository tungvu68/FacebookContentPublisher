"""Store non-secret Facebook Page connection metadata.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from facebook_content_publisher.infrastructure.database.orm import UTCDateTime, UUIDText

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if "facebook_page_connections" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "facebook_page_connections",
        sa.Column("id", UUIDText(), primary_key=True),
        sa.Column("page_id", sa.String(100), nullable=False),
        sa.Column("page_name", sa.String(200), nullable=False),
        sa.Column("credential_alias", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="CONNECTED"),
        sa.Column("permissions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("can_publish", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("can_comment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("connected_at", UTCDateTime(), nullable=False),
        sa.Column("last_validated_at", UTCDateTime()),
        sa.Column("token_expires_at", UTCDateTime()),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("last_error_message", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.UniqueConstraint("page_id", name="uq_facebook_page_connection_page"),
    )
    op.create_index("ix_facebook_page_connection_page", "facebook_page_connections", ["page_id"])


def downgrade() -> None:
    op.drop_index("ix_facebook_page_connection_page", table_name="facebook_page_connections")
    op.drop_table("facebook_page_connections")
