"""Database schema definitions for CoChairAI application."""

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text
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
    Column("title", String(500), nullable=False),
    Column("description", Text, nullable=True),
    Column("owner", String(500), nullable=True),
    Column("status", String(50), nullable=False, default="open"),
    Column("due_date", DateTime(timezone=True), nullable=True),
    Column("created_on", DateTime(timezone=True), nullable=False),
    Column("modified_on", DateTime(timezone=True), nullable=False),
)


def init_database_schema(engine: Engine) -> None:
    """Initialize database schema by creating all tables."""
    METADATA.create_all(engine)