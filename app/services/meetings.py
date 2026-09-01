from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.schemas import MeetingCreate, MinutesDraft, TopicDraft
from app.config import get_settings
from app.models.dataverse import load_dataverse_metadata
from app.models.meeting import ApprovalStatus

DRAFT = 504260000
APPROVED = 504260001


@dataclass
class ActionRecord:
    id: str
    title: str
    description: str = ""
    owner: str | None = None
    status: str = "open"


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
    guest: str | None = None
    status: str = "open"
    minutes: str = ""
    actions: list[ActionRecord] = field(default_factory=list)
    meeting: MeetingSummary = field(default_factory=lambda: MeetingSummary(""))


@dataclass
class MeetingRecord:
    id: str
    title: str
    starts_at: datetime
    duration_minutes: int
    attendees: str = ""
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    invitation_requested: bool = False
    invitation_generated: bool = False
    meeting_url: str | None = None
    topics: list[TopicRecord] = field(default_factory=list)


def _tables():
    metadata = load_dataverse_metadata(get_settings().solution_export_directory)
    return metadata.tables


def _integer(value: object, default: int = 0) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _topic_actions(database: Session, topic_id: str) -> list[ActionRecord]:
    actions = _tables()["actions_list"]
    return [ActionRecord(id=row["actions_listid"], title=row["action_title"] or row["title"] or "Untitled action", description=row["description"] or "", owner=row["owner"], status=row["status"] or "open") for row in database.execute(select(actions).where(actions.c.topic_id == topic_id)).mappings()]


def _topics(database: Session, meeting_id: str, meeting_title: str, approval_status: ApprovalStatus = ApprovalStatus.DRAFT) -> list[TopicRecord]:
    tables = _tables()
    agenda_rows = database.execute(select(tables["meeting_agendas"]).where(tables["meeting_agendas"].c.meeting_id == meeting_id)).mappings()
    topic_intake = tables["topic_intake"]
    agenda_topics = []
    for row in agenda_rows:
        intake = database.execute(select(topic_intake).where(topic_intake.c.topic_intakeid == row["topic_id"])).mappings().first()
        agenda_topics.append(
            TopicRecord(
                id=row["meeting_agendasid"],
                title=row["newcolumn"] or "Untitled topic",
                description=intake["topicdescription"] if intake else "",
                scheduled_time=row["topic_time"],
                duration_minutes=_integer(row["topic_duration"]) or None,
                board_attendees=intake["board"] if intake else "",
                cross_board_attendees=intake["xboard"] if intake else "",
                lead=intake["topic_lead"] if intake else None,
                guest=intake["guests"] if intake else None,
                status=str(row["new_topic_meeting_status"] or "open"),
                meeting=MeetingSummary(meeting_title, approval_status),
            )
        )
    minute_rows = database.execute(select(tables["topics_list"]).where(tables["topics_list"].c.meeting_id == meeting_id)).mappings()
    minute_topics = [TopicRecord(id=row["topics_listid"], title=row["topic_title"] or "Untitled topic", description=row["topic_description"] or "", scheduled_time=row["topic_time"], duration_minutes=_integer(row["duration"]) or None, board_attendees=row["board"] or "", cross_board_attendees=row["xboard"] or "", lead=row["lead"], status=row["status"] or "open", minutes=row["topic_minutes"] or "", actions=_topic_actions(database, row["topic_id"]), meeting=MeetingSummary(meeting_title, approval_status)) for row in minute_rows]
    return minute_topics + agenda_topics


def _meeting_record(database: Session, row: dict) -> MeetingRecord:
    tables = _tables()
    meeting_id = row["meetingid"]
    approval = database.scalar(select(tables["meeting_minutes"].c.approvalstatus).where(tables["meeting_minutes"].c.meeting_id == meeting_id))
    title = row["meeting_title"] or row["name"] or "Untitled meeting"
    approval_status = ApprovalStatus.APPROVED if approval == APPROVED else ApprovalStatus.DRAFT
    return MeetingRecord(id=meeting_id, title=title, starts_at=row["meeting_date"], duration_minutes=_integer(row["meeting_duration"]), attendees=row["meeting_attendees"] or "", approval_status=approval_status, invitation_requested=bool(row["new_send_invite_requested"]), invitation_generated=bool(row["new_meeting_invite_generated"]), meeting_url=row["new_teams_meeting_url"], topics=_topics(database, meeting_id, title, approval_status))


def _insert_agenda(database: Session, meeting_id: str, topic: TopicDraft, sequence: int) -> None:
    tables = _tables()
    topic_id = str(uuid4())
    database.execute(tables["topic_intake"].insert().values(topic_intakeid=topic_id, topictitle=topic.title, topicdescription=topic.description, topic_lead=topic.lead, board=topic.board_attendees, xboard=topic.cross_board_attendees, guests=topic.guest, topic_duration=str(topic.duration_minutes or ""), sequence=sequence))
    database.execute(tables["meeting_agendas"].insert().values(meeting_agendasid=str(uuid4()), meeting_id=meeting_id, topic_id=topic_id, newcolumn=topic.title, topic_time=topic.scheduled_time, topic_duration=str(topic.duration_minutes or ""), serialno=str(sequence)))


def create_topic(database: Session, meeting_id: str, payload: TopicDraft) -> TopicRecord:
    meeting = get_meeting(database, meeting_id)
    agendas = _tables()["meeting_agendas"]
    sequence = _integer(database.scalar(select(agendas.c.serialno).where(agendas.c.meeting_id == meeting_id).order_by(agendas.c.serialno.desc())), 0) + 1
    _insert_agenda(database, meeting_id, payload, sequence)
    database.commit()
    return _topics(database, meeting_id, meeting.title)[-1]


def create_meeting(database: Session, payload: MeetingCreate) -> MeetingRecord:
    tables = _tables()
    meeting_id = str(uuid4())
    database.execute(tables["meeting"].insert().values(meetingid=meeting_id, name=meeting_id, meeting_title=payload.title, meeting_date=payload.starts_at, meeting_duration=str(payload.duration_minutes), meeting_attendees=payload.attendees, new_send_invite_requested=payload.invitation_requested, new_meeting_invite_generated=False))
    for sequence, topic in enumerate(payload.topics, 1):
        _insert_agenda(database, meeting_id, topic, sequence)
    database.commit()
    return get_meeting(database, meeting_id)


def create_minutes_draft(database: Session, payload: MinutesDraft) -> MeetingRecord:
    meeting = create_meeting(database, payload)
    tables = _tables()
    database.execute(tables["meeting_minutes"].insert().values(meeting_minutesid=str(uuid4()), meeting_id=meeting.id, meeting_title=payload.title, date=payload.starts_at, duration=str(payload.duration_minutes), attendees=payload.attendees, approvalstatus=DRAFT))
    for topic in payload.topics:
        topic_id = str(uuid4())
        database.execute(tables["topics_list"].insert().values(topics_listid=str(uuid4()), topic_id=topic_id, meeting_id=meeting.id, topic_title=topic.title, topic_description=topic.description, topic_time=topic.scheduled_time, duration=topic.duration_minutes, board=topic.board_attendees, xboard=topic.cross_board_attendees, lead=topic.lead, status=topic.status, topic_minutes=topic.minutes, approvalstatus=DRAFT))
        for action in topic.actions:
            database.execute(tables["actions_list"].insert().values(actions_listid=str(uuid4()), name=str(uuid4()), topic_id=topic_id, meeting_id=meeting.id, action_title=action.title, description=action.description, owner=action.owner, approvalstatus=DRAFT))
    database.commit()
    return get_meeting(database, meeting.id)


def get_meeting(database: Session, meeting_id: str) -> MeetingRecord:
    meeting = _tables()["meeting"]
    row = database.execute(select(meeting).where(meeting.c.meetingid == meeting_id)).mappings().first()
    if row is None:
        raise LookupError(f"Meeting {meeting_id} was not found.")
    return _meeting_record(database, row)


def list_meetings(database: Session) -> list[MeetingRecord]:
    meeting = _tables()["meeting"]
    return [_meeting_record(database, row) for row in database.execute(select(meeting).order_by(meeting.c.meeting_date.desc())).mappings()]


def list_topics(database: Session) -> list[TopicRecord]:
    return [topic for meeting in list_meetings(database) for topic in meeting.topics]


def approve_meeting_minutes(database: Session, meeting_id: str) -> MeetingRecord:
    tables = _tables()
    get_meeting(database, meeting_id)
    for name in ("meeting_minutes", "topics_list", "actions_list"):
        database.execute(update(tables[name]).where(tables[name].c.meeting_id == meeting_id).values(approvalstatus=APPROVED))
    database.commit()
    return get_meeting(database, meeting_id)