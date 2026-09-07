"""Database schema definitions for CoChairAI application."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine

METADATA = MetaData()

# Meeting management table
meeting = Table(
    "meeting",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=True),
    Column("scheduled_date", DateTime(timezone=True), nullable=False),
    Column("duration_minutes", Integer, nullable=True),
    Column("attendees", Text, nullable=True),
    Column("location", String(500), nullable=True),
    Column("status", String(50), nullable=False, default="scheduled"),
    Column("invitation_requested", Boolean, nullable=False, default=False),
    Column("invitation_generated", Boolean, nullable=False, default=False),
    Column("meeting_url", String(2000), nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Column("modified_on", DateTime(timezone=True), nullable=False),
)

# Agenda planning table
topic_intake = Table(
    "topic_intake",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("meeting_id", String(36), nullable=False),
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=True),
    Column("scheduled_time", String(100), nullable=True),
    Column("duration_minutes", Integer, nullable=True),
    Column("lead", String(500), nullable=True),
    Column("board_attendees", Text, nullable=True),
    Column("cross_board_attendees", Text, nullable=True),
    Column("status", String(50), nullable=False, default="open"),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Column("modified_on", DateTime(timezone=True), nullable=False),
)

# Meeting agendas reference
meeting_agendas = Table(
    "meeting_agendas",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("meeting_id", String(36), nullable=False),
    Column("topic_id", String(36), nullable=False),
    Column("sequence", Integer, nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
)

# Meeting minutes table
meeting_minutes = Table(
    "meeting_minutes",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("meeting_id", String(36), nullable=False),
    Column("summary", Text, nullable=True),
    Column("approval_status", String(50), nullable=False, default="draft"),
    Column("approved_by", String(500), nullable=True),
    Column("approved_on", DateTime(timezone=True), nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Column("modified_on", DateTime(timezone=True), nullable=False),
)

# Topics discussed in meeting
topics_list = Table(
    "topics_list",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("meeting_minutes_id", String(36), nullable=False),
    Column("topic_id", String(36), nullable=False),
    Column("minutes", Text, nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
)

# Action items table
actions_list = Table(
    "actions_list",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("meeting_minutes_id", String(36), nullable=False),
    Column("topic_id", String(36), nullable=True),
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=True),
    Column("owner", String(500), nullable=True),
    Column("status", String(50), nullable=False, default="open"),
    Column("due_date", DateTime(timezone=True), nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Column("modified_on", DateTime(timezone=True), nullable=False),
)

# Resolved attendee identities per topic. Drives both UI visibility and the
# per-topic SharePoint folder permissions, so entries must be real directory
# principals rather than free text.
topic_attendee = Table(
    "topic_attendee",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("topic_id", String(36), nullable=False),
    Column("upn", String(320), nullable=False),
    Column("display_name", String(500), nullable=True),
    Column("object_id", String(36), nullable=True),
    Column("attendee_type", String(30), nullable=False),
    Column("created_on", DateTime(timezone=True), nullable=False),
    UniqueConstraint("topic_id", "upn", "attendee_type", name="uq_topic_attendee"),
    Index("ix_topic_attendee_topic", "topic_id"),
)

# Append-only approval history covering every level of the hierarchy.
# Current state is the most recent row for an entity; earlier rows are the audit trail.
approval = Table(
    "approval",
    METADATA,
    Column("id", String(36), primary_key=True),
    Column("entity_type", String(20), nullable=False),
    Column("entity_id", String(36), nullable=False),
    Column("status", String(30), nullable=False),
    Column("approver_upn", String(320), nullable=True),
    Column("comments", Text, nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Index("ix_approval_entity", "entity_type", "entity_id", "created_on"),
)


def init_database_schema(engine: Engine) -> None:
    """Initialize database schema by creating all tables."""
    METADATA.create_all(engine)