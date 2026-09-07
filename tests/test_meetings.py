from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

MINUTES_PAYLOAD = {
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


def _approve(client: TestClient, segment: str, entity_id: str):
    return client.post(f"/api/{segment}/{entity_id}/approvals", json={"status": "approved"})


def test_minutes_draft_creates_topics_actions_and_can_be_approved() -> None:
    with TestClient(app) as client:
        draft_response = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD)
        meeting = draft_response.json()
        topic = meeting["topics"][0]
        action = topic["actions"][0]

        _approve(client, "actions", action["id"])
        _approve(client, "topics", topic["id"])
        approval_response = client.post(f"/api/meetings/{meeting['id']}/approve")

    assert draft_response.status_code == 201
    assert meeting["approval_status"] == "draft"
    assert action["owner"] == "Platform team"
    assert approval_response.status_code == 200
    assert approval_response.json()["approval_status"] == "approved"


def test_meeting_approval_is_blocked_until_topics_are_approved() -> None:
    with TestClient(app) as client:
        meeting = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD).json()
        blocked = client.post(f"/api/meetings/{meeting['id']}/approve")

    assert blocked.status_code == 409
    assert "topic" in blocked.json()["detail"].lower()


def test_topic_approval_is_blocked_until_actions_are_resolved() -> None:
    with TestClient(app) as client:
        meeting = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD).json()
        topic = meeting["topics"][0]

        blocked = _approve(client, "topics", topic["id"])
        blockers = client.get(f"/api/topics/{topic['id']}/approval-blockers").json()

    assert blocked.status_code == 409
    assert blockers == ["Prepare integration adapter"]


def test_approval_history_records_the_approver() -> None:
    with TestClient(app) as client:
        meeting = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD).json()
        action = meeting["topics"][0]["actions"][0]

        _approve(client, "actions", action["id"])
        approval_history = client.get(f"/api/actions/{action['id']}/approvals").json()

    assert approval_history[0]["status"] == "approved"
    assert approval_history[0]["approver_upn"] == get_settings().dev_user_upn


def test_a_user_outside_the_approver_list_cannot_approve(monkeypatch) -> None:
    monkeypatch.setenv("CCHAIR_APPROVER_UPNS", "board.office@example.com")
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            meeting = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD).json()
            action = meeting["topics"][0]["actions"][0]
            forbidden = _approve(client, "actions", action["id"])

        assert forbidden.status_code == 403
    finally:
        get_settings.cache_clear()


def test_topic_attendees_replace_and_validate() -> None:
    with TestClient(app) as client:
        meeting = client.post("/api/meeting-minutes/draft", json=MINUTES_PAYLOAD).json()
        topic_id = meeting["topics"][0]["id"]

        saved = client.put(
            f"/api/topics/{topic_id}/attendees",
            json={
                "attendees": [
                    {"upn": "Chair@example.com", "attendee_type": "lead"},
                    {"upn": "member@example.com", "attendee_type": "board"},
                ]
            },
        )
        rejected = client.put(
            f"/api/topics/{topic_id}/attendees",
            json={"attendees": [{"upn": "not-a-principal", "attendee_type": "board"}]},
        )
        listed = client.get(f"/api/topics/{topic_id}/attendees").json()

    assert saved.status_code == 200
    assert rejected.status_code == 400
    assert {item["upn"] for item in listed} == {"chair@example.com", "member@example.com"}



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