"""Create SQLite tables for every Dataverse entity in an unpacked solution export."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.models.dataverse import init_dataverse_schema


def parse_arguments() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solution-directory", type=Path, default=settings.solution_export_directory)
    parser.add_argument("--database-url", default=settings.database_url)
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    engine = create_engine(arguments.database_url, connect_args={"check_same_thread": False})
    tables = init_dataverse_schema(engine, arguments.solution_directory)
    print(f"Created or verified {len(tables)} Dataverse tables.")
    for table in tables:
        print(table)


if __name__ == "__main__":
    main()