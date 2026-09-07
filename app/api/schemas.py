from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.meeting import ApprovalEntity, ApprovalStatus, AttendeeType


class ActionDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    owner: str | None = Field(default=None, max_length=255)


class TopicDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    scheduled_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    board_attendees: str = ""
    cross_board_attendees: str = ""
    lead: str | None = None
    guest: str | None = None
    status: str = "open"
    minutes: str = ""
    actions: list[ActionDraft] = Field(default_factory=list)


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    starts_at: datetime
    duration_minutes: int = Field(gt=0)
    attendees: str = ""
    location: str = ""
    invitation_requested: bool = False
    topics: list[TopicDraft] = Field(default_factory=list)


class MinutesDraft(MeetingCreate):
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT


class AgendaTopicLink(BaseModel):
    topic_id: str = Field(min_length=1)


class AgendaReorder(BaseModel):
    topic_ids: list[str] = Field(min_length=1)


class MeetingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    starts_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    attendees: str | None = None
    location: str | None = None
    invitation_requested: bool | None = None


class TopicUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    scheduled_time: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    board_attendees: str | None = None
    cross_board_attendees: str | None = None
    lead: str | None = None
    status: str | None = None


class ActionRead(ActionDraft):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str


class TopicRead(TopicDraft):
    model_config = ConfigDict(from_attributes=True)
    id: str
    actions: list[ActionRead]
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT


class AttendeeEntry(BaseModel):
    upn: str = Field(min_length=3, max_length=320)
    attendee_type: AttendeeType = AttendeeType.BOARD
    display_name: str | None = None
    object_id: str | None = None


class TopicAttendees(BaseModel):
    attendees: list[AttendeeEntry] = Field(default_factory=list)


class ApprovalDecision(BaseModel):
    status: ApprovalStatus
    comments: str | None = Field(default=None, max_length=2000)


class ApprovalRead(BaseModel):
    entity_type: ApprovalEntity
    entity_id: str
    status: ApprovalStatus
    approver_upn: str | None = None
    comments: str | None = None
    created_on: datetime


class MeetingRead(MeetingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    approval_status: ApprovalStatus
    invitation_generated: bool
    meeting_url: str | None
    topics: list[TopicRead]