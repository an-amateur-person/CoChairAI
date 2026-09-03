from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.email import EmailDeliveryError
from app.services.meetings import (
    add_topic_to_meeting,
    approve_meeting_minutes,
    create_meeting,
    create_minutes_draft,
    create_topic,
    list_meetings,
    send_meeting_invite,
    update_meeting,
    update_topic,
)
from app.api.schemas import AgendaTopicLink, MeetingCreate, MeetingRead, MeetingUpdate, MinutesDraft, TopicDraft, TopicRead, TopicUpdate

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
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
def approve_minutes(meeting_id: str, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return approve_meeting_minutes(database, meeting_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error