from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import CurrentUser, require_approver, require_user
from app.config import get_settings
from app.db import get_db
from app.models.meeting import ApprovalEntity
from app.services.approvals import (
    ApprovalError,
    current_status,
    history,
    meeting_blockers,
    record_decision,
    topic_blockers,
)
from app.services.attendees import Attendee, list_topic_attendees, set_topic_attendees
from app.services.email import EmailDeliveryError
from app.services.meetings import (
    add_topic_to_meeting,
    approve_meeting_minutes,
    create_meeting,
    create_minutes_draft,
    create_topic,
    list_meetings,
    remove_topic_from_meeting,
    reorder_meeting_agenda,
    send_meeting_invite,
    update_meeting,
    update_topic,
)
from app.api.schemas import (
    AgendaReorder,
    AgendaTopicLink,
    ApprovalDecision,
    ApprovalRead,
    AttendeeEntry,
    MeetingCreate,
    MeetingRead,
    MeetingUpdate,
    MinutesDraft,
    TopicAttendees,
    TopicDraft,
    TopicRead,
    TopicUpdate,
)

public_router = APIRouter(prefix="/api", tags=["system"])
router = APIRouter(prefix="/api", tags=["meetings"], dependencies=[Depends(require_user)])


@public_router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "application": settings.app_name}


@router.get("/meetings", response_model=list[MeetingRead])
def get_meetings(database: Session = Depends(get_db)) -> list[MeetingRead]:
    return list_meetings(database)


@router.post("/meetings", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def post_meeting(payload: MeetingCreate, database: Session = Depends(get_db)) -> MeetingRead:
    return create_meeting(database, payload)


@router.post("/meeting-minutes/draft", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def post_minutes_draft(payload: MinutesDraft, database: Session = Depends(get_db)) -> MeetingRead:
    return create_minutes_draft(database, payload)


@router.post("/meetings/{meeting_id}/topics", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def post_topic(meeting_id: str, payload: TopicDraft, database: Session = Depends(get_db)) -> TopicRead:
    try:
        return create_topic(database, meeting_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/meetings/{meeting_id}/agenda", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def post_agenda_topic(meeting_id: str, payload: AgendaTopicLink, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return add_topic_to_meeting(database, meeting_id, payload.topic_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.delete("/meetings/{meeting_id}/agenda/{topic_id}", response_model=MeetingRead)
def delete_agenda_topic(meeting_id: str, topic_id: str, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return remove_topic_from_meeting(database, meeting_id, topic_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put("/meetings/{meeting_id}/agenda/order", response_model=MeetingRead)
def put_agenda_order(meeting_id: str, payload: AgendaReorder, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return reorder_meeting_agenda(database, meeting_id, payload.topic_ids)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


@router.put("/meetings/{meeting_id}", response_model=MeetingRead)
def put_meeting(meeting_id: str, payload: MeetingUpdate, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return update_meeting(database, meeting_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put("/topics/{topic_id}", response_model=TopicRead)
def put_topic(topic_id: str, payload: TopicUpdate, database: Session = Depends(get_db)) -> TopicRead:
    try:
        return update_topic(database, topic_id, payload)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("/meetings/{meeting_id}/send-invite", response_model=MeetingRead)
def post_send_invite(meeting_id: str, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return send_meeting_invite(database, meeting_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except EmailDeliveryError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error


@router.post("/meetings/{meeting_id}/approve", response_model=MeetingRead)
def approve_minutes(
    meeting_id: str,
    database: Session = Depends(get_db),
    approver: CurrentUser = Depends(require_approver),
) -> MeetingRead:
    try:
        return approve_meeting_minutes(database, meeting_id, approver.upn)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ApprovalError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


_ENTITY_BY_SEGMENT = {
    "meetings": ApprovalEntity.MEETING,
    "topics": ApprovalEntity.TOPIC,
    "actions": ApprovalEntity.ACTION,
}


def _entity_or_404(segment: str) -> ApprovalEntity:
    entity = _ENTITY_BY_SEGMENT.get(segment)
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown approval scope '{segment}'.",
        )
    return entity


@router.post("/{segment}/{entity_id}/approvals", response_model=ApprovalRead)
def post_approval(
    segment: str,
    entity_id: str,
    payload: ApprovalDecision,
    database: Session = Depends(get_db),
    approver: CurrentUser = Depends(require_approver),
) -> ApprovalRead:
    entity = _entity_or_404(segment)
    try:
        record_decision(database, entity, entity_id, payload.status, approver.upn, payload.comments)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ApprovalError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    latest = history(database, entity, entity_id)[0]
    return ApprovalRead(
        entity_type=entity,
        entity_id=entity_id,
        status=latest.status,
        approver_upn=latest.approver_upn,
        comments=latest.comments,
        created_on=latest.created_on,
    )


@router.get("/{segment}/{entity_id}/approvals", response_model=list[ApprovalRead])
def get_approvals(
    segment: str,
    entity_id: str,
    database: Session = Depends(get_db),
) -> list[ApprovalRead]:
    entity = _entity_or_404(segment)
    return [
        ApprovalRead(
            entity_type=entity,
            entity_id=entity_id,
            status=record.status,
            approver_upn=record.approver_upn,
            comments=record.comments,
            created_on=record.created_on,
        )
        for record in history(database, entity, entity_id)
    ]


@router.get("/{segment}/{entity_id}/approval-blockers", response_model=list[str])
def get_approval_blockers(
    segment: str,
    entity_id: str,
    database: Session = Depends(get_db),
) -> list[str]:
    entity = _entity_or_404(segment)
    if entity is ApprovalEntity.TOPIC:
        return topic_blockers(database, entity_id)
    if entity is ApprovalEntity.MEETING:
        return meeting_blockers(database, entity_id)
    return []


@router.get("/topics/{topic_id}/attendees", response_model=list[AttendeeEntry])
def get_topic_attendees(topic_id: str, database: Session = Depends(get_db)) -> list[AttendeeEntry]:
    return [
        AttendeeEntry(
            upn=item.upn,
            attendee_type=item.attendee_type,
            display_name=item.display_name,
            object_id=item.object_id,
        )
        for item in list_topic_attendees(database, topic_id)
    ]


@router.put("/topics/{topic_id}/attendees", response_model=list[AttendeeEntry])
def put_topic_attendees(
    topic_id: str,
    payload: TopicAttendees,
    database: Session = Depends(get_db),
) -> list[AttendeeEntry]:
    try:
        saved = set_topic_attendees(
            database,
            topic_id,
            [
                Attendee(
                    upn=item.upn,
                    attendee_type=item.attendee_type,
                    display_name=item.display_name,
                    object_id=item.object_id,
                )
                for item in payload.attendees
            ],
        )
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return [
        AttendeeEntry(
            upn=item.upn,
            attendee_type=item.attendee_type,
            display_name=item.display_name,
            object_id=item.object_id,
        )
        for item in saved
    ]