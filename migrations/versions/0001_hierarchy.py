"""Add hierarchical approvals and structured topic attendees.

Revision ID: 0001_hierarchy
Revises:
Create Date: 2026-09-07
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_hierarchy"
down_revision = None
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {item["name"] for item in _inspector().get_columns(table)}


def upgrade() -> None:
    # The application also creates these via metadata.create_all on startup,
    # so each step is guarded to stay safe on already-provisioned databases.
    if not _has_column("actions_list", "topic_id"):
        op.add_column("actions_list", sa.Column("topic_id", sa.String(36), nullable=True))

    if not _has_table("topic_attendee"):
        op.create_table(
            "topic_attendee",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("topic_id", sa.String(36), nullable=False),
            sa.Column("upn", sa.String(320), nullable=False),
            sa.Column("display_name", sa.String(500), nullable=True),
            sa.Column("object_id", sa.String(36), nullable=True),
            sa.Column("attendee_type", sa.String(30), nullable=False),
            sa.Column("created_on", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("topic_id", "upn", "attendee_type", name="uq_topic_attendee"),
        )
        op.create_index("ix_topic_attendee_topic", "topic_attendee", ["topic_id"])

    if not _has_table("approval"):
        op.create_table(
            "approval",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("entity_type", sa.String(20), nullable=False),
            sa.Column("entity_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("approver_upn", sa.String(320), nullable=True),
            sa.Column("comments", sa.Text(), nullable=True),
            sa.Column("created_on", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_approval_entity", "approval", ["entity_type", "entity_id", "created_on"])


def downgrade() -> None:
    if _has_table("approval"):
        op.drop_index("ix_approval_entity", table_name="approval")
        op.drop_table("approval")
    if _has_table("topic_attendee"):
        op.drop_index("ix_topic_attendee_topic", table_name="topic_attendee")
        op.drop_table("topic_attendee")
    if _has_column("actions_list", "topic_id"):
        op.drop_column("actions_list", "topic_id")
