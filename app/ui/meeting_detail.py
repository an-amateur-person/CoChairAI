"""Meeting workspace showing the meeting > topic > action approval hierarchy."""

from nicegui import ui

from app.auth import read_identity
from app.db import SessionLocal
from app.models.meeting import ApprovalEntity, ApprovalStatus, AttendeeType
from app.services.approvals import (
    ApprovalError,
    current_status,
    record_decision,
    statuses_for,
    topic_blockers,
)
from app.services.attendees import Attendee, list_topic_attendees, set_topic_attendees
from app.services.meetings import get_meeting
from app.ui.home import _navigation, _page_heading

STATUS_COLOURS = {
    ApprovalStatus.DRAFT: "grey-6",
    ApprovalStatus.SUBMITTED: "amber-8",
    ApprovalStatus.APPROVED: "positive",
    ApprovalStatus.REJECTED: "negative",
}


def _status_chip(status: ApprovalStatus) -> None:
    ui.chip(status.value.title(), color=STATUS_COLOURS[status], text_color="white").props("dense")


def register_meeting_detail_page() -> None:
    @ui.page("/meetings/{meeting_id}")
    def meeting_detail_page(meeting_id: str) -> None:
        _navigation("/meetings")
        user = read_identity()

        with SessionLocal() as database:
            try:
                meeting = get_meeting(database, meeting_id)
            except LookupError:
                with ui.column().classes("w-full max-w-3xl mx-auto p-6"):
                    ui.label("Meeting not found.").classes("text-lg")
                    ui.link("Back to meetings", "/meetings").classes("text-primary")
                return

        if user is None:
            with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-3"):
                ui.label("Sign in to view this meeting.").classes("text-lg")
                ui.link("Sign in", f"/auth/login?return_to=/meetings/{meeting_id}").classes("text-primary")
            return

        may_approve = user.is_approver

        def decide(entity: ApprovalEntity, entity_id: str, status: ApprovalStatus) -> None:
            try:
                with SessionLocal() as database:
                    record_decision(database, entity, entity_id, status, user.upn)
                ui.notify(f"{entity.value.title()} marked {status.value}", type="positive")
                hierarchy.refresh()
            except ApprovalError as error:
                ui.notify(str(error), type="negative")
            except LookupError as error:
                ui.notify(str(error), type="negative")

        def open_attendee_dialog(topic_id: str, topic_title: str) -> None:
            with SessionLocal() as database:
                existing = list_topic_attendees(database, topic_id)
            as_text = "\n".join(f"{item.upn},{item.attendee_type.value}" for item in existing)

            with ui.dialog() as dialog, ui.card().classes("w-full max-w-xl p-6 gap-3"):
                ui.label(f"Attendees for {topic_title}").classes("text-lg font-semibold")
                ui.label(
                    "One per line as upn,type where type is lead, board or cross_board. "
                    "These principals become the SharePoint folder permissions for this topic."
                ).classes("text-sm text-gray-600")
                editor = ui.textarea("Attendees", value=as_text).props("outlined autogrow").classes("w-full")

                def save() -> None:
                    entries: list[Attendee] = []
                    for line in editor.value.splitlines():
                        if not line.strip():
                            continue
                        parts = [part.strip() for part in line.split(",")]
                        upn = parts[0]
                        raw_type = parts[1] if len(parts) > 1 else AttendeeType.BOARD.value
                        try:
                            attendee_type = AttendeeType(raw_type)
                        except ValueError:
                            ui.notify(f"Unknown attendee type '{raw_type}'", type="negative")
                            return
                        entries.append(Attendee(upn=upn, attendee_type=attendee_type))
                    try:
                        with SessionLocal() as database:
                            set_topic_attendees(database, topic_id, entries)
                    except (LookupError, ValueError) as error:
                        ui.notify(str(error), type="negative")
                        return
                    dialog.close()
                    ui.notify("Attendees updated", type="positive")
                    hierarchy.refresh()

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")
                    ui.button("Save", on_click=save)
            dialog.open()

        @ui.refreshable
        def hierarchy() -> None:
            with SessionLocal() as database:
                current = get_meeting(database, meeting_id)
                meeting_status = current_status(database, ApprovalEntity.MEETING, meeting_id)
                topic_ids = [topic.id for topic in current.topics]
                action_ids = [action.id for topic in current.topics for action in topic.actions]
                topic_statuses = statuses_for(database, ApprovalEntity.TOPIC, topic_ids)
                action_statuses = statuses_for(database, ApprovalEntity.ACTION, action_ids)
                blockers = {topic.id: topic_blockers(database, topic.id) for topic in current.topics}
                attendees = {topic.id: list_topic_attendees(database, topic.id) for topic in current.topics}

            with ui.card().classes("cochair-surface w-full p-5 gap-2"):
                with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(current.title).classes("text-xl font-semibold")
                        _status_chip(meeting_status)
                    with ui.row().classes("items-center gap-2"):
                        approve_meeting = ui.button(
                            "Approve meeting",
                            icon="task_alt",
                            on_click=lambda: decide(
                                ApprovalEntity.MEETING, meeting_id, ApprovalStatus.APPROVED
                            ),
                        )
                        approve_meeting.set_enabled(may_approve)
                        outstanding = [
                            topic.title
                            for topic in current.topics
                            if topic_statuses.get(topic.id) != ApprovalStatus.APPROVED
                        ]
                        if outstanding:
                            approve_meeting.tooltip("Pending topics: " + ", ".join(outstanding))
                ui.label(
                    f"{current.starts_at:%d %b %Y, %H:%M} · {len(current.topics)} topic(s)"
                ).classes("text-sm text-gray-600")

            if not current.topics:
                ui.label("No topics on this agenda yet.").classes("text-sm text-gray-600")
                return

            for topic in current.topics:
                topic_status = topic_statuses.get(topic.id, ApprovalStatus.DRAFT)
                with ui.card().classes("cochair-surface w-full p-5 gap-3"):
                    with ui.row().classes("w-full items-center justify-between flex-wrap gap-2"):
                        with ui.row().classes("items-center gap-3"):
                            ui.label(topic.title).classes("text-lg font-medium")
                            _status_chip(topic_status)
                        with ui.row().classes("items-center gap-2"):
                            ui.button(
                                "Attendees",
                                icon="group",
                                on_click=lambda t=topic: open_attendee_dialog(t.id, t.title),
                            ).props("flat dense")
                            reject_topic = ui.button(
                                "Reject",
                                on_click=lambda t=topic: decide(
                                    ApprovalEntity.TOPIC, t.id, ApprovalStatus.REJECTED
                                ),
                            ).props("flat dense color=negative")
                            reject_topic.set_enabled(may_approve)
                            approve_topic = ui.button(
                                "Approve topic",
                                icon="check",
                                on_click=lambda t=topic: decide(
                                    ApprovalEntity.TOPIC, t.id, ApprovalStatus.APPROVED
                                ),
                            ).props("dense")
                            approve_topic.set_enabled(may_approve and not blockers[topic.id])
                            if blockers[topic.id]:
                                approve_topic.tooltip(
                                    "Unresolved actions: " + ", ".join(blockers[topic.id])
                                )

                    people = attendees[topic.id]
                    ui.label(
                        "Attendees: " + ", ".join(item.upn for item in people)
                        if people
                        else "Attendees: not scoped yet — this topic is visible to everyone."
                    ).classes("text-sm text-gray-600")

                    if not topic.actions:
                        ui.label("No actions recorded.").classes("text-sm text-gray-500")
                        continue

                    ui.separator()
                    for action in topic.actions:
                        action_status = action_statuses.get(action.id, ApprovalStatus.DRAFT)
                        with ui.row().classes("w-full items-center justify-between gap-2 flex-wrap"):
                            with ui.row().classes("items-center gap-3 flex-1 min-w-64"):
                                ui.icon("subdirectory_arrow_right", size="xs").classes("text-gray-500")
                                ui.label(action.title).classes("text-sm")
                                ui.label(action.owner or "Unassigned").classes("text-sm text-gray-500")
                                _status_chip(action_status)
                            with ui.row().classes("items-center gap-1"):
                                reject_action = ui.button(
                                    "Reject",
                                    on_click=lambda a=action: decide(
                                        ApprovalEntity.ACTION, a.id, ApprovalStatus.REJECTED
                                    ),
                                ).props("flat dense color=negative")
                                approve_action = ui.button(
                                    "Approve",
                                    on_click=lambda a=action: decide(
                                        ApprovalEntity.ACTION, a.id, ApprovalStatus.APPROVED
                                    ),
                                ).props("flat dense")
                                reject_action.set_enabled(may_approve)
                                approve_action.set_enabled(may_approve)

        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-5"):
            _page_heading(
                "Meeting workspace",
                "Approve actions, then topics, then the meeting itself.",
                "account_tree",
            )
            if not may_approve:
                ui.label(
                    f"Signed in as {user.upn}. You have read-only access; approvals are restricted."
                ).classes("text-sm text-amber-700")
            hierarchy()
