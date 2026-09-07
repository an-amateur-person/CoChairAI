"""Resolved topic attendee identities.

Attendees drive both in-app topic visibility and, later, the per-topic SharePoint
folder permissions, so they are stored as directory principals rather than free text.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.dataverse import topic_attendee, topic_intake
from app.models.meeting import AttendeeType

UPN_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Attendee:
    upn: str
    attendee_type: AttendeeType
    display_name: str | None = None
    object_id: str | None = None


def parse_attendee_text(value: str | None) -> list[str]:
    """Extract candidate principals from legacy semicolon or comma separated text."""
    if not value:
        return []
    candidates = [part.strip() for part in re.split(r"[;,\n]", value)]
    seen: set[str] = set()
    parsed: list[str] = []
    for candidate in candidates:
        normalized = candidate.lower()
        if normalized and UPN_PATTERN.match(normalized) and normalized not in seen:
            seen.add(normalized)
            parsed.append(normalized)
    return parsed


def list_topic_attendees(database: Session, topic_id: str) -> list[Attendee]:
    rows = database.execute(
        select(
            topic_attendee.c.upn,
            topic_attendee.c.attendee_type,
            topic_attendee.c.display_name,
            topic_attendee.c.object_id,
        )
        .where(topic_attendee.c.topic_id == topic_id)
        .order_by(topic_attendee.c.attendee_type, topic_attendee.c.upn)
    ).all()
    return [
        Attendee(
            upn=upn,
            attendee_type=AttendeeType(attendee_type),
            display_name=display_name,
            object_id=object_id,
        )
        for upn, attendee_type, display_name, object_id in rows
    ]


def attendee_upns(database: Session, topic_id: str) -> set[str]:
    return {attendee.upn for attendee in list_topic_attendees(database, topic_id)}


def set_topic_attendees(database: Session, topic_id: str, attendees: list[Attendee]) -> list[Attendee]:
    """Replace the attendee list for a topic."""
    if database.execute(select(topic_intake.c.id).where(topic_intake.c.id == topic_id)).first() is None:
        raise LookupError(f"Topic {topic_id} was not found.")

    invalid = [item.upn for item in attendees if not UPN_PATTERN.match(item.upn.lower())]
    if invalid:
        raise ValueError("These attendees are not valid principals: " + ", ".join(invalid))

    now = datetime.now(timezone.utc)
    database.execute(delete(topic_attendee).where(topic_attendee.c.topic_id == topic_id))

    seen: set[tuple[str, str]] = set()
    for item in attendees:
        key = (item.upn.lower(), item.attendee_type.value)
        if key in seen:
            continue
        seen.add(key)
        database.execute(
            topic_attendee.insert().values(
                id=str(uuid4()),
                topic_id=topic_id,
                upn=item.upn.lower(),
                display_name=item.display_name,
                object_id=item.object_id,
                attendee_type=item.attendee_type.value,
                created_on=now,
            )
        )
    database.commit()
    return list_topic_attendees(database, topic_id)


def backfill_from_legacy_text(database: Session, topic_id: str) -> list[Attendee]:
    """Seed structured attendees from the legacy free-text columns on a topic."""
    row = database.execute(
        select(topic_intake.c.lead, topic_intake.c.board_attendees, topic_intake.c.cross_board_attendees)
        .where(topic_intake.c.id == topic_id)
    ).first()
    if row is None:
        raise LookupError(f"Topic {topic_id} was not found.")

    lead_text, board_text, cross_text = row
    attendees = [
        *[Attendee(upn=upn, attendee_type=AttendeeType.LEAD) for upn in parse_attendee_text(lead_text)],
        *[Attendee(upn=upn, attendee_type=AttendeeType.BOARD) for upn in parse_attendee_text(board_text)],
        *[
            Attendee(upn=upn, attendee_type=AttendeeType.CROSS_BOARD)
            for upn in parse_attendee_text(cross_text)
        ],
    ]
    return set_topic_attendees(database, topic_id, attendees)


def user_may_view_topic(database: Session, topic_id: str, upn: str) -> bool:
    """A topic with no recorded attendees stays visible; once scoped, only attendees may view."""
    attendees = attendee_upns(database, topic_id)
    return not attendees or upn.lower() in attendees
