from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.meetings import approve_meeting_minutes, create_meeting, create_minutes_draft, create_topic, list_meetings
from app.api.schemas import MeetingCreate, MeetingRead, MinutesDraft, TopicDraft, TopicRead

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


@router.post("/meetings/{meeting_id}/approve", response_model=MeetingRead)
def approve_minutes(meeting_id: str, database: Session = Depends(get_db)) -> MeetingRead:
    try:
        return approve_meeting_minutes(database, meeting_id)
    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error