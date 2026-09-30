"""Add dynamic prompt profile and translation token metadata.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    country_columns = {item["name"] for item in inspector.get_columns("country_profiles")}
    with op.batch_alter_table("country_profiles") as batch:
        if "native_reader_label" not in country_columns:
            batch.add_column(sa.Column("native_reader_label", sa.String(100), nullable=True))
        if "localization_level" not in country_columns:
            batch.add_column(
                sa.Column(
                    "localization_level", sa.String(20), nullable=False, server_default="natural"
                )
            )
    localized_columns = {item["name"] for item in inspector.get_columns("localized_contents")}
    with op.batch_alter_table("localized_contents") as batch:
        for name in ("input_tokens", "output_tokens", "cached_input_tokens"):
            if name not in localized_columns:
                batch.add_column(sa.Column(name, sa.Integer(), nullable=True))
    op.execute(
        "UPDATE country_profiles SET native_reader_label = language_name "
        "WHERE native_reader_label IS NULL OR native_reader_label = ''"
    )
    op.execute(
        "UPDATE country_profiles SET language_name = 'Brazilian Portuguese', "
        "native_reader_label = 'Brazilian Portuguese speaker' WHERE language_code = 'pt-BR'"
    )


def downgrade() -> None:
    with op.batch_alter_table("localized_contents") as batch:
        batch.drop_column("cached_input_tokens")
        batch.drop_column("output_tokens")
        batch.drop_column("input_tokens")
    with op.batch_alter_table("country_profiles") as batch:
        batch.drop_column("localization_level")
        batch.drop_column("native_reader_label")
