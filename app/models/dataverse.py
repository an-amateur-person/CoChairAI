"""Generate SQLite-compatible Dataverse tables from an unpacked solution export."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, inspect, text
from sqlalchemy.engine import Engine

DATAVERSE_METADATA = MetaData()


def _table_name(entity_name: str) -> str:
    return entity_name.lower().removeprefix("cr882_")


def _column_name(logical_name: str) -> str:
    return logical_name.lower().removeprefix("cr882_")


def _column_type(attribute: ElementTree.Element):
    attribute_type = attribute.findtext("Type", default="nvarchar")
    if attribute_type in {"bit"}:
        return Boolean
    if attribute_type in {"int", "picklist", "state", "status"}:
        return Integer
    if attribute_type == "datetime":
        return DateTime(timezone=True)
    if attribute_type in {"primarykey", "lookup", "owner"}:
        return String(36)
    max_length = attribute.findtext("MaxLength")
    if max_length and int(max_length) <= 4_000:
        return String(int(max_length))
    return Text


def _solution_file(export_directory: Path) -> Path | None:
    candidates = sorted(Path(export_directory).glob("*/customizations.xml"))
    return candidates[0] if len(candidates) == 1 else None


def load_dataverse_metadata(export_directory: Path) -> MetaData:
    """Read the unique unpacked solution manifest into SQLAlchemy table metadata."""
    source_file = _solution_file(export_directory)
    if source_file is None:
        return DATAVERSE_METADATA

    root = ElementTree.parse(source_file).getroot()
    for entity in root.findall("./Entities/Entity"):
        entity_definition = entity.find("./EntityInfo/entity")
        if entity_definition is None:
            continue
        table_name = _table_name(entity_definition.attrib["Name"])
        if table_name in DATAVERSE_METADATA.tables:
            continue
        columns = []
        for attribute in entity_definition.findall("./attributes/attribute"):
            logical_name = attribute.findtext("LogicalName")
            if not logical_name:
                continue
            is_primary_key = attribute.findtext("Type") == "primarykey"
            columns.append(
                Column(
                    _column_name(logical_name),
                    _column_type(attribute),
                    primary_key=is_primary_key,
                    nullable=not is_primary_key,
                )
            )
        if columns:
            Table(table_name, DATAVERSE_METADATA, *columns)
    return DATAVERSE_METADATA


def init_dataverse_schema(engine: Engine, export_directory: Path) -> list[str]:
    metadata = load_dataverse_metadata(export_directory)
    existing_tables = set(inspect(engine).get_table_names())
    for table_name in metadata.tables:
        previous_name = f"cr882_{table_name}"
        if previous_name in existing_tables and table_name not in existing_tables:
            with engine.begin() as connection:
                connection.execute(text(f'ALTER TABLE "{previous_name}" RENAME TO "{table_name}"'))
    for table_name, table in metadata.tables.items():
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspect(engine).get_columns(table_name)}
        for column_name in table.columns.keys():
            previous_name = f"cr882_{column_name}"
            if previous_name in existing_columns and column_name not in existing_columns:
                with engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE "{table_name}" RENAME COLUMN "{previous_name}" TO "{column_name}"'))
    metadata.create_all(engine)
    return list(metadata.tables)