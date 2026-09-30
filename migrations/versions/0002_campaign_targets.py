"""Add campaign country targets.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from facebook_content_publisher.infrastructure.database.orm import UTCDateTime, UUIDText

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("campaign_targets"):
        return
    op.create_table(
        "campaign_targets",
        sa.Column("id", UUIDText(), nullable=False),
        sa.Column("campaign_id", UUIDText(), nullable=False),
        sa.Column("country_profile_id", UUIDText(), nullable=False),
        sa.Column("link_override", sa.Text(), nullable=True),
        sa.Column("comment_delay_minutes", sa.Integer(), nullable=False),
        sa.Column("delayed_comment_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "publish_mode", sa.Enum("IMMEDIATE", "SCHEDULED", name="publishmode"), nullable=False
        ),
        sa.Column("scheduled_at_utc", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["country_profile_id"], ["country_profiles.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "country_profile_id", name="uq_campaign_target_country"),
    )
    op.create_index("ix_campaign_targets_campaign_id", "campaign_targets", ["campaign_id"])
    op.create_index(
        "ix_campaign_targets_country_profile_id", "campaign_targets", ["country_profile_id"]
    )


def downgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("campaign_targets"):
        return
    op.drop_index("ix_campaign_targets_country_profile_id", table_name="campaign_targets")
    op.drop_index("ix_campaign_targets_campaign_id", table_name="campaign_targets")
    op.drop_table("campaign_targets")
