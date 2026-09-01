from sqlalchemy import create_engine, inspect

from app.models.dataverse import init_dataverse_schema


def test_importer_creates_every_exported_dataverse_table() -> None:
    engine = create_engine("sqlite://")
    tables = init_dataverse_schema(engine, "data/unpacked")

    inspector = inspect(engine)
    assert set(tables) == {
        "actions_list",
        "meeting",
        "meeting_agendas",
        "meeting_minutes",
        "meetingagenda",
        "topic_intake",
        "topics_list",
        "new_topic_folder_registry",
    }
    assert {column["name"] for column in inspector.get_columns("meeting")} >= {
        "meetingid",
        "meeting_title",
        "meeting_date",
        "new_teams_meeting_url",
    }


def test_importer_renames_existing_prefixed_columns() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE meeting (cr882_meetingid TEXT PRIMARY KEY, cr882_meeting_title TEXT)"
        )

    init_dataverse_schema(engine, "data/unpacked")

    column_names = {column["name"] for column in inspect(engine).get_columns("meeting")}
    assert "meetingid" in column_names
    assert "meeting_title" in column_names
    assert "cr882_meetingid" not in column_names
    assert "cr882_meeting_title" not in column_names