from datetime import datetime

from nicegui import app, ui

from app.api.schemas import MeetingCreate, MeetingUpdate, TopicDraft, TopicUpdate
from app.config import get_settings
from app.db import SessionLocal
from app.services.email import EmailDeliveryError
from app.services.meetings import (
    add_topic_to_meeting,
    create_meeting,
    create_topic,
    get_meeting,
    list_meetings,
    list_topics,
    send_meeting_invite,
    update_meeting,
    update_topic,
)


def _apply_theme() -> ui.dark_mode:
    ui.colors(primary="#A100FF", secondary="#7500C0", accent="#FF6B00", positive="#16803C")
    # None follows the OS/browser color scheme until the user picks a preference explicitly
    dark_mode = ui.dark_mode(value=app.storage.user.get("dark_mode"))
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

            /* Dark mode: deep purple undertones instead of near-black, softer contrast with brand accents */
            body.body--dark { background: #1B1425; color: #E8E1F0; }
            body.body--dark .cochair-header { background: #170F20; }
            body.body--dark .cochair-brand-mark { background: #B94BFF; }
            body.body--dark .cochair-nav-active { background: rgba(185, 75, 255, .2); }
            body.body--dark .cochair-metric { border-top-color: #B94BFF; box-shadow: 0 8px 24px rgba(10, 4, 20, .5); }
            body.body--dark .cochair-surface { border-color: #3D2E52; box-shadow: 0 8px 24px rgba(10, 4, 20, .4); }
            body.body--dark .cochair-table { border-color: #3D2E52; background: #241A33; }
            body.body--dark .q-card { background: #241A33; color: #E8E1F0; }
            body.body--dark .q-card.cochair-metric { background: #241A33; }
            body.body--dark .q-date { background: #241A33 !important; color: #E8E1F0; }
            body.body--dark .q-date__header { background: #2E2144 !important; }
            body.body--dark .q-date__calendar-item, body.body--dark .q-date__view { background: transparent; }
            body.body--dark .text-gray-500 { color: #A99BC0 !important; }
            body.body--dark .text-gray-600 { color: #BCAFD4 !important; }
            body.body--dark .text-gray-700 { color: #D3C8E5 !important; }
        </style>
        """
    )
    return dark_mode


def _theme_icon(value: bool | None) -> str:
    if value is None:
        return "brightness_auto"
    return "dark_mode" if value else "light_mode"


def _navigation(active_path: str) -> None:
    dark_mode = _apply_theme()
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

            def toggle_theme() -> None:
                # cycle: auto (follow system) -> dark -> light -> auto
                cycle: list[bool | None] = [None, True, False]
                new_value = cycle[(cycle.index(dark_mode.value) + 1) % len(cycle)] if dark_mode.value in cycle else True
                dark_mode.value = new_value
                if new_value is None:
                    app.storage.user.pop("dark_mode", None)
                else:
                    app.storage.user["dark_mode"] = new_value
                theme_button.props(f"icon={_theme_icon(new_value)}")

            theme_button = ui.button(icon=_theme_icon(dark_mode.value), on_click=toggle_theme).props("flat round")
            theme_button.tooltip("Theme: click to cycle auto / dark / light")
            theme_button.classes("text-white/70")


def _meeting_rows() -> list[dict[str, str | int]]:
    with SessionLocal() as database:
        meetings = list_meetings(database)
        return [
            {
                "id": meeting.id,
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
        {"name": "actions", "label": "", "field": "actions"},
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

            def open_meeting_dialog(meeting_id: str) -> None:
                with SessionLocal() as database:
                    mtg = get_meeting(database, meeting_id)
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-6 gap-3"):
                    ui.label(f"Edit meeting: {mtg.title}").classes("text-lg font-semibold")
                    attendees_input = ui.textarea("Attendees", value=mtg.attendees).classes("w-full")
                    with ui.row().classes("w-full gap-4"):
                        duration_input = ui.number("Duration (minutes)", value=mtg.duration_minutes or 0, min=1, precision=0).classes("flex-1")
                        location_input = ui.input("Location", value=mtg.location).classes("flex-1")

                    ui.separator()
                    agenda_section = ui.column().classes("w-full gap-2")

                    def render_agenda_section() -> None:
                        agenda_section.clear()
                        with SessionLocal() as database:
                            current = get_meeting(database, meeting_id)
                            all_topics = list_topics(database)
                        with agenda_section:
                            ui.label(f"Agenda topics ({len(current.topics)})").classes("font-medium")
                            if not current.topics:
                                ui.label("No topics yet. Add one below.").classes("text-sm text-gray-600")
                            for topic in current.topics:
                                with ui.row().classes("w-full items-center justify-between"):
                                    ui.label(f"{topic.title} · {topic.lead or 'No lead'}").classes("text-sm")
                                    ui.label(f"{topic.duration_minutes or '-'} min · {topic.status.title()}").classes("text-sm text-gray-600")

                            attached_ids = {topic.id for topic in current.topics}
                            available_topics = {
                                topic.id: f"{topic.title} — {topic.meeting.title}"
                                for topic in all_topics
                                if topic.id not in attached_ids
                            }

                            with ui.row().classes("w-full gap-2 items-end mt-2 flex-wrap"):
                                topic_choice = ui.select(available_topics, label="Existing topic").classes("flex-1 min-w-56")

                                def add_existing_topic() -> None:
                                    try:
                                        if not topic_choice.value:
                                            raise ValueError("Select a topic to add")
                                        with SessionLocal() as database:
                                            add_topic_to_meeting(database, meeting_id, topic_choice.value)
                                        render_agenda_section()
                                        table.rows = rows_with_add()
                                        table.update()
                                        ui.notify("Topic added to agenda")
                                    except (LookupError, ValueError) as error:
                                        ui.notify(f"Unable to add topic: {error}", type="negative")

                                ui.button("Add to agenda", on_click=add_existing_topic, icon="playlist_add")
                            if not available_topics:
                                ui.label("No other topics available. Create new topics from the Topics page.").classes("text-sm text-gray-600")

                            def send_invite() -> None:
                                try:
                                    with SessionLocal() as database:
                                        send_meeting_invite(database, meeting_id)
                                    ui.notify("Invitation sent", type="positive")
                                    dialog.close()
                                except (LookupError, ValueError) as error:
                                    ui.notify(str(error), type="warning")
                                except EmailDeliveryError as error:
                                    ui.notify(str(error), type="negative")

                            with ui.row().classes("w-full items-center justify-between mt-2"):
                                invite_button = ui.button("Send invite", on_click=send_invite, icon="mail")
                                invite_button.set_enabled(bool(current.topics))
                                if not current.topics:
                                    invite_button.tooltip("Add at least one agenda topic before sending an invite.")
                                if current.invitation_generated:
                                    ui.label("Invitation already sent").classes("text-sm text-positive")

                    render_agenda_section()

                    def save_meeting_details() -> None:
                        try:
                            payload = MeetingUpdate(
                                attendees=attendees_input.value,
                                duration_minutes=int(duration_input.value) if duration_input.value else None,
                                location=location_input.value,
                            )
                            with SessionLocal() as database:
                                update_meeting(database, meeting_id, payload)
                            table.rows = rows_with_add()
                            table.update()
                            ui.notify("Meeting updated")
                            dialog.close()
                        except (LookupError, ValueError) as error:
                            ui.notify(f"Unable to update meeting: {error}", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")
                        ui.button("Save changes", on_click=save_meeting_details, icon="save")
                dialog.open()

            def open_create_meeting_dialog() -> None:
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-6 gap-3"):
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
                            table.rows = rows_with_add()
                            table.update()
                            ui.notify("Meeting created")
                            dialog.close()
                        except (TypeError, ValueError) as error:
                            ui.notify(f"Unable to create meeting: {error}", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")
                        ui.button("Create meeting", on_click=save_meeting, icon="add")
                dialog.open()

            def rows_with_add() -> list[dict[str, str | int]]:
                return [*_meeting_rows(), {"id": "__add__"}]

            table = ui.table(columns=_meeting_columns(include_attendees=True), rows=rows_with_add(), row_key="id").classes("cochair-table w-full")
            table.add_slot(
                "body",
                '''
                <q-tr v-if="props.row.id === '__add__'" class="cursor-pointer text-primary" @click="() => $parent.$emit('add_meeting')">
                    <q-td colspan="100%">
                        <q-icon name="add" size="xs" class="q-mr-sm" />Schedule meeting
                    </q-td>
                </q-tr>
                <q-tr v-else :props="props">
                    <q-td v-for="col in props.cols" :key="col.name" :props="props">
                        <q-btn v-if="col.name === 'actions'" round flat dense icon="edit" color="primary" @click="() => $parent.$emit('edit_meeting', props.row)" />
                        <template v-else>{{ col.value }}</template>
                    </q-td>
                </q-tr>
                ''',
            )
            table.on("edit_meeting", lambda event: open_meeting_dialog(event.args["id"]))
            table.on("add_meeting", lambda _: open_create_meeting_dialog())

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
                {"name": "actions_count", "label": "Actions", "field": "actions_count"},
                {"name": "actions", "label": "", "field": "actions"},
            ]

            def topic_rows() -> list[dict[str, str | int]]:
                with SessionLocal() as database:
                    return [
                        {
                            "id": topic.id,
                            "meeting": topic.meeting.title,
                            "title": topic.title,
                            "lead": topic.lead or "-",
                            "duration": topic.duration_minutes or "-",
                            "status": topic.status.title(),
                            "actions_count": len(topic.actions),
                        }
                        for topic in list_topics(database)
                    ]

            def open_topic_dialog(topic_id: str) -> None:
                with SessionLocal() as database:
                    selected_topic = next((topic for topic in list_topics(database) if topic.id == topic_id), None)
                if selected_topic is None:
                    ui.notify("Topic not found", type="negative")
                    return
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-6 gap-3"):
                    ui.label(f"Edit topic: {selected_topic.title}").classes("text-lg font-semibold")
                    edit_title = ui.input("Topic title", value=selected_topic.title).classes("w-full")
                    edit_description = ui.textarea("Description", value=selected_topic.description).classes("w-full")
                    with ui.row().classes("w-full gap-4"):
                        edit_scheduled_time = ui.input("Scheduled time", value=selected_topic.scheduled_time or "").classes("flex-1")
                        edit_duration = ui.number("Duration (minutes)", value=selected_topic.duration_minutes or 0, min=0, precision=0).classes("flex-1")
                    edit_lead = ui.input("Topic lead", value=selected_topic.lead or "").classes("w-full")
                    edit_status = ui.select(["open", "in_progress", "closed"], value=selected_topic.status, label="Status").classes("w-full")

                    def save_edit() -> None:
                        try:
                            payload = TopicUpdate(
                                title=edit_title.value,
                                description=edit_description.value,
                                scheduled_time=edit_scheduled_time.value or None,
                                duration_minutes=int(edit_duration.value) if edit_duration.value is not None else None,
                                lead=edit_lead.value or None,
                                status=edit_status.value,
                            )
                            with SessionLocal() as database:
                                update_topic(database, topic_id, payload)
                            table.rows = rows_with_add()
                            table.update()
                            ui.notify("Topic updated")
                            dialog.close()
                        except (LookupError, ValueError) as error:
                            ui.notify(f"Unable to update topic: {error}", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")
                        ui.button("Save changes", on_click=save_edit, icon="save")
                dialog.open()

            with SessionLocal() as database:
                meeting_choices = {meeting.id: meeting.title for meeting in list_meetings(database)}

            def open_create_topic_dialog() -> None:
                with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl p-6 gap-3"):
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
                            table.rows = rows_with_add()
                            table.update()
                            ui.notify("Agenda topic added")
                            dialog.close()
                        except (TypeError, ValueError) as error:
                            ui.notify(f"Unable to add topic: {error}", type="negative")

                    with ui.row().classes("w-full justify-end gap-2 mt-4"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")
                        ui.button("Add topic", on_click=save_topic, icon="add")
                dialog.open()

            def rows_with_add() -> list[dict[str, str | int]]:
                return [*topic_rows(), {"id": "__add__"}]

            table = ui.table(columns=columns, rows=rows_with_add(), row_key="id").classes("cochair-table w-full")
            table.add_slot(
                "body",
                '''
                <q-tr v-if="props.row.id === '__add__'" class="cursor-pointer text-primary" @click="() => $parent.$emit('add_topic')">
                    <q-td colspan="100%">
                        <q-icon name="add" size="xs" class="q-mr-sm" />Add agenda topic
                    </q-td>
                </q-tr>
                <q-tr v-else :props="props">
                    <q-td v-for="col in props.cols" :key="col.name" :props="props">
                        <q-btn v-if="col.name === 'actions'" round flat dense icon="edit" color="primary" @click="() => $parent.$emit('edit_topic', props.row)" />
                        <template v-else>{{ col.value }}</template>
                    </q-td>
                </q-tr>
                ''',
            )
            table.on("edit_topic", lambda event: open_topic_dialog(event.args["id"]))
            table.on("add_topic", lambda _: open_create_topic_dialog())

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
