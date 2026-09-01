# CoChairAI

A configuration-driven starter for migrating Power Platform solution exports into a Python application. It uses FastAPI, NiceGUI, SQLite with SQLAlchemy and Alembic, and APScheduler.

## Setup

Requires Python 3.12.

```powershell
cd powerplatform-python-migration
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure runtime paths, database connection, UI secret, scheduler timezone, and import limits in `.env`.

## Run

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000` for the UI and `http://127.0.0.1:8000/api/health` for the health endpoint.

## Import a solution export

Place a solution zip in `data/import`, then run:

```powershell
python scripts/unpack_solution.py data/import/solution.zip
```

Use `--help` to configure output location and size limits. The script rejects invalid archives, symbolic links, and unsafe extraction paths.

## Migrations and tests

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
pytest
```

## Imported Dataverse tables

At startup, CoChairAI reads the single solution found below `PPM_SOLUTION_EXPORT_DIRECTORY` and creates SQLite-compatible tables using every exported Dataverse logical table and column name. Run the importer separately when needed:

```powershell
python scripts/import_dataverse_schema.py
```

Imported table and column names remove the `cr882_` publisher prefix, for example `meeting.meeting_title` and `topic_intake.topictitle`. Dataverse GUID, lookup, owner, choice, date, number, and text types are mapped to SQLite-compatible storage types. CoChairAI reads and writes these migrated tables for its meeting workflows.

The exported `SAP_Meeting_Solution` core is represented by native Meeting, Topic, and Action Item models. See `docs/solution-migration.md` for the artifact mapping and extension boundaries for Teams, SharePoint, and AI providers.

## Layout

- `app/api`: HTTP endpoints
- `app/ui`: NiceGUI pages
- `app/models`: SQLAlchemy models
- `app/services`: migration services
- `app/workflows`: background and flow jobs
- `app/agents`: agent integration boundaries
- `app/config`: environment-backed settings
- `migrations`: Alembic environment and revisions
- `scripts`: operational utilities
- `tests`: automated tests
- `data/import`: incoming solution export archives