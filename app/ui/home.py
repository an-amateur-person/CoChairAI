from datetime import datetime

from nicegui import ui

from app.api.schemas import MeetingCreate, TopicDraft
from app.config import get_settings
from app.db import SessionLocal
from app.services.meetings import create_meeting, create_topic, list_meetings, list_topics


def _apply_theme() -> None:
    ui.colors(primary="#A100FF", secondary="#7500C0", accent="#FF6B00", positive="#16803C")
    ui.add_head_html(
        """
        <style>
            body { background: #F7F5FA; color: #1F1B24; }
            .cochair-header { background: #1F1B24; }
            .cochair-brand-mark { background: #A100FF; border-radius: 8px; }
            .cochair-nav-active { background: rgba(161, 0, 255, .26); border-radius: 6px; }
            .cochair-metric { border-top: 3px solid #A100FF; box-shadow: 0 8px 24px rgba(31, 27, 36, .08); }
            .cochair-surface { border: 1px solid #E6E0EA; box-shadow: 0 8px 24px rgba(31, 27, 36, .06); }
            .cochair-table { border: 1px solid #E6E0EA; border-radius: 8px; overflow: hidden; background: white; }
        </style>
        """
    )


def _navigation(active_path: str) -> None:
    _apply_theme()
    ui.page_title(get_settings().app_name)
    with ui.header().classes("cochair-header items-center justify-between px-4 md:px-8 shadow-sm"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("groups", size="sm").classes("cochair-brand-mark p-2 text-white")
            ui.label(get_settings().app_name).classes("text-lg font-semibold text-white")
        with ui.row().classes("items-center gap-1"):
            for label, icon, path in (
                ("Dashboard", "dashboard", "/"),
                ("Meetings", "event", "/meetings"),
                ("Topics", "format_list_bulleted", "/topics"),
                ("Minutes", "description", "/minutes"),
            ):
                button = ui.button(icon=icon, on_click=lambda route=path: ui.navigate.to(route)).props("flat round")
                button.tooltip(label)
                button.classes("text-white" if path == active_path else "text-white/70")
                if path == active_path:
                    button.classes("cochair-nav-active")


def _meeting_rows() -> list[dict[str, str | int]]:
    with SessionLocal() as database:
        meetings = list_meetings(database)
        return [
            {
                "title": meeting.title,
                "starts_at": meeting.starts_at.strftime("%d %b %Y, %H:%M"),
                "duration": meeting.duration_minutes,
                "attendees": meeting.attendees or "-",
                "status": meeting.approval_status.title(),
                "topics": len(meeting.topics),
            }
            for meeting in meetings
        ]


def _meeting_columns(include_attendees: bool = False) -> list[dict[str, str]]:
    columns = [
        {"name": "title", "label": "Meeting", "field": "title", "align": "left"},
        {"name": "starts_at", "label": "Scheduled", "field": "starts_at", "align": "left"},
        {"name": "duration", "label": "Minutes", "field": "duration"},
        {"name": "status", "label": "Minutes status", "field": "status"},
        {"name": "topics", "label": "Topics", "field": "topics"},
    ]
    if include_attendees:
        columns.insert(3, {"name": "attendees", "label": "Attendees", "field": "attendees", "align": "left"})
    return columns


def _page_heading(title: str, description: str, icon: str | None = None, icon_size: str = "2rem") -> None:
    with ui.row().classes("items-center gap-3"):
        if icon:
            ui.icon(icon, size=icon_size).classes("text-primary")
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-3xl font-semibold")
            ui.label(description).classes("text-gray-600")


def _metric_card(label: str, value: int, icon: str, path: str) -> None:
    with ui.card().classes("cochair-metric w-56 max-w-full p-5"):
        with ui.row().classes("w-full items-start justify-between"):
            ui.label(label).classes("text-sm font-medium text-gray-600")
            ui.icon(icon, size="sm").classes("text-primary")
        ui.label(str(value)).classes("text-4xl font-semibold mt-3")
        button = ui.button(icon="arrow_forward", on_click=lambda: ui.navigate.to(path)).props("flat round dense")
        button.tooltip(f"Open {label.lower()}")
        button.classes("self-end text-primary")


def _summary_panel(title: str, icon: str | None, path: str, entries: list[tuple[str, str]]) -> None:
    with ui.card().classes("cochair-surface flex-1 min-w-72 p-5"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-2"):
                if icon:
                    ui.icon(icon, size="sm").classes("text-primary")
                ui.label(title).classes("text-lg font-semibold")
            ui.link("View all", path).classes("text-sm font-medium text-primary")
        if entries:
            with ui.column().classes("w-full gap-0 mt-3"):
                for index, (primary, secondary) in enumerate(entries):
                    if index:
                        ui.separator()
                    with ui.column().classes("w-full gap-0 py-3"):
                        ui.label(primary).classes("font-medium")
                        ui.label(secondary).classes("text-sm text-gray-600")
        else:
            ui.label("Nothing to show yet.").classes("text-sm text-gray-600 mt-5 mb-3")


def _calendar_panel(meetings: list) -> None:
    meeting_days = {meeting.starts_at.date().isoformat() for meeting in meetings}
    selected_day = datetime.now().astimezone().date().isoformat()
    with ui.card().classes("cochair-surface w-full p-5"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("calendar_month", size="sm").classes("text-primary")
            ui.label("Meeting calendar").classes("text-lg font-semibold")
        with ui.row().classes("w-full gap-6 flex-wrap items-start mt-3"):
            calendar = ui.date(value=selected_day).props("flat bordered minimal").classes("min-w-72")
            calendar.props(f':events="{sorted(meeting_days)}" event-color="primary"')
            selection = ui.column().classes("flex-1 min-w-72 justify-center gap-2")

            def refresh_selection() -> None:
                selection.clear()
                selected_meetings = [meeting for meeting in meetings if meeting.starts_at.date().isoformat() == calendar.value]
                with selection:
                    ui.label(datetime.fromisoformat(calendar.value).strftime("%A, %d %B")).classes("font-medium text-gray-700")
                    if not selected_meetings:
                        ui.label("No meetings scheduled for this date.").classes("text-sm text-gray-600 mt-3")
                    else:
                        ui.label(f"{len(selected_meetings)} meeting{'s' if len(selected_meetings) != 1 else ''} scheduled").classes("text-2xl font-semibold text-primary mt-2")
                        ui.label("Highlighted dates indicate scheduled meetings.").classes("text-sm text-gray-600")
                        ui.link("View meetings", "/meetings").classes("text-sm font-medium text-primary mt-2")

            calendar.on("update:model-value", lambda _: refresh_selection())
            refresh_selection()
        if meeting_days:
            ui.label(f"{len(meeting_days)} meeting date{'s' if len(meeting_days) != 1 else ''} scheduled").classes("text-xs text-gray-500 mt-2")


def register_home_page() -> None:
    @ui.page("/")
    def dashboard_page() -> None:
        _navigation("/")
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
            _page_heading("Dashboard", "Scheduled board meetings, agenda topics, and captured minutes.")
            with SessionLocal() as database:
                meetings = list_meetings(database)
                topics = list_topics(database)
            minutes_count = sum(1 for topic in topics if topic.minutes.strip())
            with ui.row().classes("w-full gap-4 flex-wrap"):
                _metric_card("Scheduled meetings", len(meetings), "event", "/meetings")
                _metric_card("Agenda topics", len(topics), "format_list_bulleted", "/topics")
                _metric_card("Minutes captured", minutes_count, "description", "/minutes")
            _calendar_panel(meetings)
            now = datetime.now().astimezone()
            next_meetings = sorted(
                (meeting for meeting in meetings if meeting.starts_at.astimezone() >= now),
                key=lambda meeting: meeting.starts_at,
            )[:5]
            latest_topics = list(reversed(topics))[:5]
            latest_minutes = [topic for topic in reversed(topics) if topic.minutes.strip()][:5]
            with ui.row().classes("w-full gap-5 flex-wrap items-stretch"):
                _summary_panel(
                    "Upcoming Meetings",
                    "calendar_month",
                    "/meetings",
                    [(meeting.title, meeting.starts_at.strftime("%d %b %Y, %H:%M")) for meeting in next_meetings],
                )
                _summary_panel(
                    "Planned Topics",
                    "format_list_bulleted",
                    "/topics",
                    [(topic.title, topic.meeting.title) for topic in latest_topics],
                )
                _summary_panel(
                    "Meeting Minutes captured",
                    "description",
                    "/minutes",
                    [(topic.title, topic.meeting.title) for topic in latest_minutes],
                )

    @ui.page("/meetings")
    def meetings_page() -> None:
        _navigation("/meetings")
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
            _page_heading("Meetings", "Create and review scheduled board meetings.", "event")
            table = ui.table(columns=_meeting_columns(include_attendees=True), rows=_meeting_rows()).classes("cochair-table w-full")
            with ui.card().classes("cochair-surface w-full max-w-2xl p-6"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("add_circle", size="sm").classes("text-primary")
                    ui.label("Schedule meeting").classes("text-lg font-semibold")
                title = ui.input("Meeting title").classes("w-full")
                starts_at = ui.input("Start (ISO 8601)", value=datetime.now().astimezone().replace(microsecond=0).isoformat()).classes("w-full")
                duration = ui.number("Duration (minutes)", value=60, min=1, precision=0).classes("w-full")
                attendees = ui.textarea("Attendees", placeholder="person@example.com; other@example.com").classes("w-full")

                def save_meeting() -> None:
                    try:
                        payload = MeetingCreate(title=title.value, starts_at=starts_at.value, duration_minutes=int(duration.value), attendees=attendees.value)
                        with SessionLocal() as database:
                            create_meeting(database, payload)
                        table.rows = _meeting_rows()
                        table.update()
                        ui.notify("Meeting created")
                    except (TypeError, ValueError) as error:
                        ui.notify(f"Unable to create meeting: {error}", type="negative")

                ui.button("Create meeting", on_click=save_meeting, icon="add").classes("self-start")

    @ui.page("/topics")
    def topics_page() -> None:
        _navigation("/topics")
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
            _page_heading("Topics", "Agenda topics and their owners across all meetings.", "format_list_bulleted")
            columns = [
                {"name": "meeting", "label": "Meeting", "field": "meeting", "align": "left"},
                {"name": "title", "label": "Topic", "field": "title", "align": "left"},
                {"name": "lead", "label": "Lead", "field": "lead", "align": "left"},
                {"name": "duration", "label": "Duration", "field": "duration"},
                {"name": "status", "label": "Status", "field": "status"},
                {"name": "actions", "label": "Actions", "field": "actions"},
            ]
            table = ui.table(columns=columns, rows=[]).classes("cochair-table w-full")

            def topic_rows() -> list[dict[str, str | int]]:
                with SessionLocal() as database:
                    return [
                        {
                            "meeting": topic.meeting.title,
                            "title": topic.title,
                            "lead": topic.lead or "-",
                            "duration": topic.duration_minutes or "-",
                            "status": topic.status.title(),
                            "actions": len(topic.actions),
                        }
                        for topic in list_topics(database)
                    ]

            table.rows = topic_rows()
            table.update()
            with SessionLocal() as database:
                meeting_choices = {meeting.id: meeting.title for meeting in list_meetings(database)}
            with ui.card().classes("cochair-surface w-full max-w-2xl p-6"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("add_circle", size="sm").classes("text-primary")
                    ui.label("Add agenda topic").classes("text-lg font-semibold")
                meeting_id = ui.select(meeting_choices, label="Meeting").classes("w-full")
                title = ui.input("Topic title").classes("w-full")
                description = ui.textarea("Description").classes("w-full")
                with ui.row().classes("w-full gap-4"):
                    scheduled_time = ui.input("Scheduled time").classes("flex-1")
                    duration = ui.number("Duration (minutes)", min=1, precision=0).classes("flex-1")
                lead = ui.input("Topic lead").classes("w-full")
                board_attendees = ui.textarea("Board attendees").classes("w-full")

                def save_topic() -> None:
                    try:
                        if not meeting_id.value:
                            raise ValueError("Select a meeting")
                        payload = TopicDraft(
                            title=title.value,
                            description=description.value,
                            scheduled_time=scheduled_time.value or None,
                            duration_minutes=int(duration.value) if duration.value else None,
                            lead=lead.value or None,
                            board_attendees=board_attendees.value,
                        )
                        with SessionLocal() as database:
                            create_topic(database, meeting_id.value, payload)
                        table.rows = topic_rows()
                        table.update()
                        ui.notify("Agenda topic added")
                    except (TypeError, ValueError) as error:
                        ui.notify(f"Unable to add topic: {error}", type="negative")

                ui.button("Add topic", on_click=save_topic, icon="add").classes("self-start")

    @ui.page("/minutes")
    def minutes_page() -> None:
        _navigation("/minutes")
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-6"):
            _page_heading("Meeting minutes", "Draft and approved minutes captured for meeting topics.", "description")
            with SessionLocal() as database:
                topics = list_topics(database)
                rows = [
                    {
                        "meeting": topic.meeting.title,
                        "topic": topic.title,
                        "minutes": topic.minutes,
                        "actions": len(topic.actions),
                        "approval": topic.meeting.approval_status.title(),
                    }
                    for topic in topics
                    if topic.minutes.strip()
                ]
            columns = [
                {"name": "meeting", "label": "Meeting", "field": "meeting", "align": "left"},
                {"name": "topic", "label": "Topic", "field": "topic", "align": "left"},
                {"name": "minutes", "label": "Minutes", "field": "minutes", "align": "left"},
                {"name": "actions", "label": "Actions", "field": "actions"},
                {"name": "approval", "label": "Approval", "field": "approval"},
            ]
            if rows:
                ui.table(columns=columns, rows=rows).classes("cochair-table w-full")
            else:
                with ui.card().classes("cochair-surface w-full p-6 items-center"):
                    ui.icon("description", size="lg").classes("text-primary")
                    ui.label("No meeting minutes have been captured yet.").classes("text-gray-600")
