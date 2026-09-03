import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.schemas import MeetingCreate, MeetingUpdate, MinutesDraft, TopicDraft, TopicUpdate
from app.models.dataverse import meeting, topic_intake, meeting_agendas, meeting_minutes, topics_list, actions_list
from app.models.meeting import ApprovalStatus
from app.services.email import send_email


@dataclass
class ActionRecord:
    id: str
    title: str
    description: str = ""
    owner: str | None = None
    status: str = "open"
    due_date: datetime | None = None


@dataclass
class MeetingSummary:
    title: str
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT


@dataclass
class TopicRecord:
    id: str
    title: str
    description: str = ""
    scheduled_time: str | None = None
    duration_minutes: int | None = None
    board_attendees: str = ""
    cross_board_attendees: str = ""
    lead: str | None = None
    status: str = "open"
    minutes: str = ""
    actions: list[ActionRecord] = field(default_factory=list)
    meeting: MeetingSummary = field(default_factory=lambda: MeetingSummary(""))


@dataclass
class MeetingRecord:
    id: str
    title: str
    starts_at: datetime
    duration_minutes: int | None = None
    attendees: str = ""
    location: str = ""
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    description: str = ""
    invitation_requested: bool = False
    invitation_generated: bool = False
    meeting_url: str | None = None
    topics: list[TopicRecord] = field(default_factory=list)


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _get_approval_status(status_str: str) -> ApprovalStatus:
    """Convert status string to ApprovalStatus enum."""
    return ApprovalStatus.APPROVED if status_str == ApprovalStatus.APPROVED else ApprovalStatus.DRAFT


def _topic_actions(database: Session, meeting_minutes_id: str) -> list[ActionRecord]:
    """Fetch all actions for a meeting minutes record."""
    rows = database.execute(
        select(actions_list).where(actions_list.c.meeting_minutes_id == meeting_minutes_id)
    ).mappings().all()
    return [
        ActionRecord(
            id=row.get("id", str(uuid4())),
            title=row.get("title", "Untitled action"),
            description=row.get("description", ""),
            owner=row.get("owner"),
            status=row.get("status", "open"),
            due_date=row.get("due_date")
        )
        for row in rows
    ]


def _topics(database: Session, meeting_id: str, meeting_title: str, approval_status: ApprovalStatus = ApprovalStatus.DRAFT) -> list[TopicRecord]:
    """Fetch all topics for a meeting."""
    from sqlalchemy import join
    
    # Get topics from meeting_agendas joined with topic_intake
    stmt = select(
        topic_intake.c.id,
        topic_intake.c.title,
        topic_intake.c.description,
        topic_intake.c.scheduled_time,
        topic_intake.c.duration_minutes,
        topic_intake.c.board_attendees,
        topic_intake.c.cross_board_attendees,
        topic_intake.c.lead,
        topic_intake.c.status,
    ).select_from(
        join(meeting_agendas, topic_intake, meeting_agendas.c.topic_id == topic_intake.c.id)
    ).where(meeting_agendas.c.meeting_id == meeting_id).order_by(meeting_agendas.c.sequence, topic_intake.c.created_on)
    
    agenda_rows = database.execute(stmt).mappings().all()
    
    topic_records = []
    for row in agenda_rows:
        minutes_link = database.execute(
            select(topics_list.c.meeting_minutes_id, topics_list.c.minutes)
            .where(topics_list.c.topic_id == row["id"])
            .order_by(topics_list.c.created_on.desc())
        ).first()
        topic_minutes = minutes_link.minutes if minutes_link else ""
        topic_actions = _topic_actions(database, minutes_link.meeting_minutes_id) if minutes_link else []
        topic_records.append(
            TopicRecord(
                id=row.get("id", str(uuid4())),
                title=row.get("title", "Untitled topic"),
                description=row.get("description", ""),
                scheduled_time=row.get("scheduled_time"),
                duration_minutes=_integer(row.get("duration_minutes")),
                board_attendees=row.get("board_attendees", ""),
                cross_board_attendees=row.get("cross_board_attendees", ""),
                lead=row.get("lead"),
                status=row.get("status", "open"),
                minutes=topic_minutes,
                actions=topic_actions,
                meeting=MeetingSummary(meeting_title, approval_status)
            )
        )
    
    # Get topics from topics_list (captured minutes)
    minute_rows = database.execute(
        select(topics_list).where(topics_list.c.meeting_minutes_id == 
               select(meeting_minutes.c.id).where(meeting_minutes.c.meeting_id == meeting_id).correlate_except(topics_list).scalar_subquery()
        )
    ).mappings().all()
    
    for row in minute_rows:
        mm_id = row.get("meeting_minutes_id", str(uuid4()))
        topic_records.append(
            TopicRecord(
                id=row.get("id", str(uuid4())),
                title=row.get("title", "Untitled topic"),
                description=row.get("description", ""),
                scheduled_time=row.get("scheduled_time"),
                duration_minutes=_integer(row.get("duration_minutes")),
                board_attendees=row.get("board_attendees", ""),
                cross_board_attendees=row.get("cross_board_attendees", ""),
                lead=row.get("lead"),
                status=row.get("status", "open"),
                minutes=row.get("minutes", ""),
                actions=_topic_actions(database, mm_id),
                meeting=MeetingSummary(meeting_title, approval_status)
            )
        )
    
    return topic_records


def _meeting_record(database: Session, row: dict) -> MeetingRecord:
    """Convert database row to MeetingRecord."""
    meeting_id = row.get("id")
    
    # Check approval status
    minute_row = database.execute(
        select(meeting_minutes).where(meeting_minutes.c.meeting_id == meeting_id)
    ).mappings().first()
    
    approval_status = ApprovalStatus.DRAFT
    if minute_row:
        status_str = minute_row.get("approval_status", ApprovalStatus.DRAFT)
        approval_status = _get_approval_status(status_str)
    
    return MeetingRecord(
        id=meeting_id,
        title=row.get("title", "Untitled meeting"),
        starts_at=row.get("scheduled_date"),
        duration_minutes=_integer(row.get("duration_minutes")),
        attendees=row.get("attendees", ""),
        location=row.get("location", ""),
        description=row.get("description", ""),
        approval_status=approval_status,
        invitation_requested=row.get("invitation_requested", False),
        invitation_generated=row.get("invitation_generated", False),
        meeting_url=row.get("meeting_url"),
        topics=_topics(database, meeting_id, row.get("title", "Untitled meeting"), approval_status)
    )


def create_topic(database: Session, meeting_id: str, payload: TopicDraft) -> TopicRecord:
    """Add a topic to a meeting."""
    meeting_row = database.execute(
        select(meeting).where(meeting.c.id == meeting_id)
    ).mappings().first()
    
    if not meeting_row:
        raise LookupError(f"Meeting {meeting_id} not found")
    
    topic_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    database.execute(
        topic_intake.insert().values(
            id=topic_id,
            meeting_id=meeting_id,
            title=payload.title,
            description=payload.description,
            scheduled_time=payload.scheduled_time,
            duration_minutes=payload.duration_minutes,
            lead=payload.lead,
            board_attendees=payload.board_attendees,
            cross_board_attendees=payload.cross_board_attendees,
            created_on=now,
            modified_on=now
        )
    )
    
    database.execute(
        meeting_agendas.insert().values(
            id=str(uuid4()),
            meeting_id=meeting_id,
            topic_id=topic_id,
            sequence=(database.scalar(
                select(meeting_agendas.c.sequence)
                .where(meeting_agendas.c.meeting_id == meeting_id)
                .order_by(meeting_agendas.c.sequence.desc())
            ) or 0) + 1,
            created_on=now
        )
    )
    database.commit()
    
    meeting_record = _meeting_record(database, meeting_row)
    return meeting_record.topics[-1] if meeting_record.topics else TopicRecord(id=topic_id, title=payload.title)


def add_topic_to_meeting(database: Session, meeting_id: str, topic_id: str) -> MeetingRecord:
    """Attach an existing topic to a meeting's agenda."""
    meeting_row = database.execute(select(meeting).where(meeting.c.id == meeting_id)).mappings().first()
    if meeting_row is None:
        raise LookupError(f"Meeting {meeting_id} was not found.")

    topic_row = database.execute(select(topic_intake).where(topic_intake.c.id == topic_id)).mappings().first()
    if topic_row is None:
        raise LookupError(f"Topic {topic_id} was not found.")

    already_linked = database.execute(
        select(meeting_agendas.c.id).where(
            meeting_agendas.c.meeting_id == meeting_id,
            meeting_agendas.c.topic_id == topic_id,
        )
    ).first()
    if already_linked:
        raise ValueError("This topic is already on the meeting agenda.")

    database.execute(
        meeting_agendas.insert().values(
            id=str(uuid4()),
            meeting_id=meeting_id,
            topic_id=topic_id,
            created_on=datetime.now(timezone.utc),
        )
    )
    database.commit()
    return get_meeting(database, meeting_id)


def _normalize_agenda_sequences(database: Session, meeting_id: str) -> None:
    """Keep agenda sequence values contiguous after an item is removed."""
    links = database.execute(
        select(meeting_agendas.c.id)
        .where(meeting_agendas.c.meeting_id == meeting_id)
        .order_by(meeting_agendas.c.sequence, meeting_agendas.c.created_on)
    ).scalars().all()
    for sequence, agenda_id in enumerate(links, 1):
        database.execute(
            update(meeting_agendas).where(meeting_agendas.c.id == agenda_id).values(sequence=sequence)
        )


def create_meeting(database: Session, payload: MeetingCreate) -> MeetingRecord:
    """Create a new meeting with optional topics."""
    meeting_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    database.execute(
        meeting.insert().values(
            id=meeting_id,
            title=payload.title,
            scheduled_date=payload.starts_at,
            duration_minutes=payload.duration_minutes,
            attendees=payload.attendees,
            location=payload.location if hasattr(payload, 'location') else "",
            status="scheduled",
            created_on=now,
            modified_on=now
        )
    )
    
    for topic_payload in payload.topics or []:
        create_topic(database, meeting_id, topic_payload)
    
    database.commit()
    return get_meeting(database, meeting_id)


def create_minutes_draft(database: Session, payload: MinutesDraft) -> MeetingRecord:
    """Create meeting minutes draft."""
    meeting_obj = create_meeting(database, payload)
    now = datetime.now(timezone.utc)
    
    mm_id = str(uuid4())
    database.execute(
        meeting_minutes.insert().values(
            id=mm_id,
            meeting_id=meeting_obj.id,
            summary=payload.title if hasattr(payload, 'title') else "",
            approval_status=ApprovalStatus.DRAFT,
            created_on=now,
            modified_on=now
        )
    )
    
    for topic in payload.topics or []:
        topic_record = next((item for item in meeting_obj.topics if item.title == topic.title), None)
        topic_id = topic_record.id if topic_record else str(uuid4())
        database.execute(
            topics_list.insert().values(
                id=str(uuid4()),
                meeting_minutes_id=mm_id,
                topic_id=topic_id,
                minutes=topic.minutes if hasattr(topic, 'minutes') else "",
                created_on=now
            )
        )
        
        for action in topic.actions if hasattr(topic, 'actions') else []:
            database.execute(
                actions_list.insert().values(
                    id=str(uuid4()),
                    meeting_minutes_id=mm_id,
                    title=action.title,
                    description=action.description if hasattr(action, 'description') else "",
                    owner=action.owner if hasattr(action, 'owner') else None,
                    status=action.status if hasattr(action, 'status') else "open",
                    created_on=now,
                    modified_on=now
                )
            )
    
    database.commit()
    return get_meeting(database, meeting_obj.id)


def save_minutes_draft(database: Session, meeting_id: str, minutes_text: str) -> MeetingRecord:
    """Create or replace the draft minutes for an existing meeting."""
    if database.execute(select(meeting).where(meeting.c.id == meeting_id)).first() is None:
        raise LookupError(f"Meeting {meeting_id} was not found.")

    now = datetime.now(timezone.utc)
    existing = database.execute(
        select(meeting_minutes.c.id).where(meeting_minutes.c.meeting_id == meeting_id)
    ).scalar_one_or_none()
    if existing:
        database.execute(
            update(meeting_minutes).where(meeting_minutes.c.id == existing).values(
                summary=minutes_text,
                approval_status=ApprovalStatus.DRAFT,
                approved_by=None,
                approved_on=None,
                modified_on=now,
            )
        )
    else:
        database.execute(
            meeting_minutes.insert().values(
                id=str(uuid4()),
                meeting_id=meeting_id,
                summary=minutes_text,
                approval_status=ApprovalStatus.DRAFT,
                created_on=now,
                modified_on=now,
            )
        )
    database.commit()
    return get_meeting(database, meeting_id)


def get_minutes_draft(database: Session, meeting_id: str) -> str:
    """Return the latest saved minutes text for a meeting."""
    row = database.execute(
        select(meeting_minutes.c.summary)
        .where(meeting_minutes.c.meeting_id == meeting_id)
        .order_by(meeting_minutes.c.created_on.desc())
    ).first()
    return row[0] if row and row[0] else ""


def get_meeting(database: Session, meeting_id: str) -> MeetingRecord:
    """Retrieve a meeting by ID."""
    row = database.execute(
        select(meeting).where(meeting.c.id == meeting_id)
    ).mappings().first()
    
    if row is None:
        raise LookupError(f"Meeting {meeting_id} was not found.")
    
    return _meeting_record(database, row)


def list_meetings(database: Session) -> list[MeetingRecord]:
    """List all meetings ordered by date."""
    rows = database.execute(
        select(meeting).order_by(meeting.c.scheduled_date.desc())
    ).mappings().all()
    
    return [_meeting_record(database, row) for row in rows]


def list_topics(database: Session) -> list[TopicRecord]:
    """List all topics across all meetings."""
    return [topic for mtg in list_meetings(database) for topic in mtg.topics]


def update_meeting(database: Session, meeting_id: str, payload: MeetingUpdate) -> MeetingRecord:
    """Update editable meeting details such as attendees, duration, and location."""
    existing = database.execute(select(meeting).where(meeting.c.id == meeting_id)).mappings().first()
    if existing is None:
        raise LookupError(f"Meeting {meeting_id} was not found.")

    updates = payload.model_dump(exclude_none=True)
    if "starts_at" in updates:
        updates["scheduled_date"] = updates.pop("starts_at")

    if updates:
        updates["modified_on"] = datetime.now(timezone.utc)
        database.execute(update(meeting).where(meeting.c.id == meeting_id).values(**updates))
        database.commit()

    return get_meeting(database, meeting_id)


def update_topic(database: Session, topic_id: str, payload: TopicUpdate) -> TopicRecord:
    """Update editable topic details such as title, lead, status, and duration."""
    existing = database.execute(select(topic_intake).where(topic_intake.c.id == topic_id)).mappings().first()
    if existing is None:
        raise LookupError(f"Topic {topic_id} was not found.")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        updates["modified_on"] = datetime.now(timezone.utc)
        database.execute(update(topic_intake).where(topic_intake.c.id == topic_id).values(**updates))
        database.commit()

    agenda_row = database.execute(
        select(meeting_agendas.c.meeting_id).where(meeting_agendas.c.topic_id == topic_id)
    ).mappings().first()
    if agenda_row is None:
        raise LookupError(f"Topic {topic_id} is not linked to a meeting agenda.")

    mtg = get_meeting(database, agenda_row["meeting_id"])
    updated_topic = next((topic for topic in mtg.topics if topic.id == topic_id), None)
    if updated_topic is None:
        raise LookupError(f"Topic {topic_id} was not found after update.")
    return updated_topic


def send_meeting_invite(database: Session, meeting_id: str) -> MeetingRecord:
    """Send a meeting invitation email once an agenda has been created."""
    mtg = get_meeting(database, meeting_id)
    if not mtg.topics:
        raise ValueError("Add at least one agenda topic before sending an invite.")

    recipients = [address.strip() for address in re.split(r"[;,]", mtg.attendees) if address.strip()]
    if not recipients:
        raise ValueError("Add at least one attendee email address before sending an invite.")

    subject = f"Meeting invite: {mtg.title}"
    agenda_lines = "\n".join(
        f"- {topic.title} ({topic.duration_minutes or '?'} min, lead: {topic.lead or 'TBD'})" for topic in mtg.topics
    )
    body = (
        f"You are invited to '{mtg.title}'.\n"
        f"When: {mtg.starts_at.strftime('%A, %d %B %Y at %H:%M')}\n"
        f"Duration: {mtg.duration_minutes} minutes\n"
        f"Location: {mtg.location or 'TBD'}\n\n"
        f"Agenda:\n{agenda_lines}"
    )

    send_email(recipients, subject, body)

    database.execute(
        update(meeting).where(meeting.c.id == meeting_id).values(
            invitation_generated=True,
            modified_on=datetime.now(timezone.utc),
        )
    )
    database.commit()
    return get_meeting(database, meeting_id)


def approve_meeting_minutes(database: Session, meeting_id: str) -> MeetingRecord:
    """Approve meeting minutes."""
    mtg = get_meeting(database, meeting_id)
    now = datetime.now(timezone.utc)
    
    # Update meeting_minutes approval status
    database.execute(
        update(meeting_minutes).where(meeting_minutes.c.meeting_id == meeting_id).values(
            approval_status=ApprovalStatus.APPROVED,
            approved_on=now,
            modified_on=now,
        )
    )
    
    # Update related topics and actions
    mm_ids = database.execute(
        select(meeting_minutes.c.id).where(meeting_minutes.c.meeting_id == meeting_id)
    ).scalars().all()
    
    for mm_id in mm_ids:
        database.execute(
            update(actions_list).where(actions_list.c.meeting_minutes_id == mm_id).values(
                status="approved",
                modified_on=now,
            )
        )
    
    database.commit()
    return get_meeting(database, meeting_id)


def remove_topic_from_meeting(database: Session, meeting_id: str, topic_id: str) -> MeetingRecord:
    """Remove a topic from an agenda without deleting the reusable topic."""
    link = database.execute(
        select(meeting_agendas.c.id).where(
            meeting_agendas.c.meeting_id == meeting_id,
            meeting_agendas.c.topic_id == topic_id,
        )
    ).scalar_one_or_none()
    if link is None:
        raise LookupError(f"Topic {topic_id} is not on meeting {meeting_id}'s agenda.")
    database.execute(meeting_agendas.delete().where(meeting_agendas.c.id == link))
    _normalize_agenda_sequences(database, meeting_id)
    database.commit()
    return get_meeting(database, meeting_id)


def reorder_meeting_agenda(database: Session, meeting_id: str, topic_ids: list[str]) -> MeetingRecord:
    """Persist the displayed topic order for a meeting agenda."""
    agenda_ids = set(database.execute(
        select(meeting_agendas.c.topic_id).where(meeting_agendas.c.meeting_id == meeting_id)
    ).scalars().all())
    if set(topic_ids) != agenda_ids or len(topic_ids) != len(agenda_ids):
        raise ValueError("The reordered topic list must contain each agenda topic exactly once.")
    for sequence, topic_id in enumerate(topic_ids, 1):
        database.execute(
            update(meeting_agendas).where(
                meeting_agendas.c.meeting_id == meeting_id,
                meeting_agendas.c.topic_id == topic_id,
            ).values(sequence=sequence)
        )
    database.commit()
    return get_meeting(database, meeting_id)