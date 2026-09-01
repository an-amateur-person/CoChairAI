from fastapi.testclient import TestClient

from app.main import app


def test_minutes_draft_creates_topics_actions_and_can_be_approved() -> None:
    payload = {
        "title": "Migration steering meeting",
        "starts_at": "2026-09-01T09:00:00+00:00",
        "duration_minutes": 60,
        "attendees": "chair@example.com; secretary@example.com",
        "topics": [
            {
                "title": "Solution migration",
                "minutes": "Reviewed the migration plan.",
                "actions": [{"title": "Prepare integration adapter", "owner": "Platform team"}],
            }
        ],
    }

    with TestClient(app) as client:
        draft_response = client.post("/api/meeting-minutes/draft", json=payload)
        meeting = draft_response.json()
        approval_response = client.post(f"/api/meetings/{meeting['id']}/approve")

    assert draft_response.status_code == 201
    assert meeting["approval_status"] == "draft"
    assert meeting["topics"][0]["actions"][0]["owner"] == "Platform team"
    assert approval_response.status_code == 200
    assert approval_response.json()["approval_status"] == "approved"


def test_topic_can_be_added_to_an_existing_meeting() -> None:
    meeting_payload = {
        "title": "Topic planning meeting",
        "starts_at": "2026-09-02T09:00:00+00:00",
        "duration_minutes": 45,
    }
    topic_payload = {"title": "Security update", "duration_minutes": 15, "lead": "Risk lead"}

    with TestClient(app) as client:
        meeting_response = client.post("/api/meetings", json=meeting_payload)
        topic_response = client.post(f"/api/meetings/{meeting_response.json()['id']}/topics", json=topic_payload)

    assert topic_response.status_code == 201
    assert topic_response.json()["title"] == "Security update"
    assert topic_response.json()["lead"] == "Risk lead"