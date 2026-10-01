"""Add translation workflow lifecycle metadata.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from facebook_content_publisher.infrastructure.database.orm import UTCDateTime

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("localized_contents")}
    definitions = {
        "provider_request_id": sa.Column("provider_request_id", sa.String(100)),
        "translation_started_at": sa.Column("translation_started_at", UTCDateTime()),
        "translation_completed_at": sa.Column("translation_completed_at", UTCDateTime()),
        "failure_code": sa.Column("failure_code", sa.String(100)),
        "failure_message": sa.Column("failure_message", sa.Text()),
        "source_text_hash": sa.Column(
            "source_text_hash", sa.String(64), nullable=False, server_default=""
        ),
        "manually_edited": sa.Column(
            "manually_edited", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        "rejected_at": sa.Column("rejected_at", UTCDateTime()),
    }
    with op.batch_alter_table("localized_contents") as batch:
        for name, column in definitions.items():
            if name not in columns:
                batch.add_column(column)
    unique_names = {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("localized_contents")
    }
    if "uq_localized_campaign_country" not in unique_names:
        with op.batch_alter_table("localized_contents") as batch:
            batch.create_unique_constraint(
                "uq_localized_campaign_country", ["campaign_id", "country_profile_id"]
            )


def downgrade() -> None:
    with op.batch_alter_table("localized_contents") as batch:
        batch.drop_constraint("uq_localized_campaign_country", type_="unique")
        for name in (
            "rejected_at",
            "manually_edited",
            "source_text_hash",
            "failure_message",
            "failure_code",
            "translation_completed_at",
            "translation_started_at",
            "provider_request_id",
        ):
            batch.drop_column(name)
