# CoChairAI

CoChairAI is a meeting-governance workspace for planning board meetings, organizing agenda topics, capturing meeting minutes, and tracking follow-up actions in one place.

The application provides a focused operational view of meetings from preparation through minutes approval. Its FastAPI backend and NiceGUI interface use a local SQLite database, with all application settings supplied through environment configuration.

## What It Does

- **Dashboard summary:** Monitor scheduled meetings, planned topics, and captured minutes. The dashboard highlights upcoming meetings and the latest topic and minutes activity, with direct links to each workspace.
- **Meeting planning:** Create scheduled meetings with a date, duration, and attendee list.
- **Topic intake:** Add agenda topics to an existing meeting with scheduling, duration, lead, description, and board-attendee details.
- **Meeting minutes:** Store topic-level minutes with associated actions, owners, and approval status.
- **Approvals:** Move captured minutes from draft to approved through the API workflow.
- **Workflow readiness:** APScheduler initializes a configurable reminder scan, ready for a notification adapter such as Microsoft Graph, Teams, or email.

## Application Screens

| Screen | Purpose |
| --- | --- |
| Dashboard | High-level operational summary: Upcoming Meetings, Planned Topics, and Meeting Minutes captured |
| Meetings | View scheduled meetings and create a new meeting |
| Topics | View agenda topics and add a topic to an existing meeting |
| Meeting minutes | View captured topic minutes, related action count, and approval status |

## Technology

- Python 3.12
- FastAPI for the HTTP API
- NiceGUI for the web interface
- SQLite and SQLAlchemy for local persistence
- Alembic for schema migrations
- APScheduler for background workflow jobs
- pydantic-settings for environment-based configuration
- pytest for automated validation

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

## API Workflows

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Check application health and configured name |
| `GET` | `/api/meetings` | List scheduled meetings and their topics |
| `POST` | `/api/meetings` | Create a meeting, optionally with agenda topics |
| `POST` | `/api/meetings/{meeting_id}/topics` | Add an agenda topic to a meeting |
| `POST` | `/api/meeting-minutes/draft` | Create a meeting-minutes draft with topics and actions |
| `POST` | `/api/meetings/{meeting_id}/approve` | Approve the meeting minutes and related records |

## Configuration

Copy `.env.example` to `.env` and configure the values for the local environment:

| Setting | Purpose |
| --- | --- |
| `PPM_APP_NAME` | Browser and application display name |
| `PPM_DATABASE_URL` | SQLAlchemy database URL |
| `PPM_UI_STORAGE_SECRET` | NiceGUI session-storage secret |
| `PPM_SCHEDULER_TIMEZONE` | Timezone for background jobs |
| `PPM_REMINDER_SCAN_INTERVAL_MINUTES` | Reminder scan cadence |
| `PPM_SOLUTION_EXPORT_DIRECTORY` | Directory containing the unpacked solution metadata |

## Data Model

CoChairAI uses prefix-free Dataverse-derived tables for its core workflow:

- `meeting` for scheduled meeting records and invitation state
- `topic_intake` and `meeting_agendas` for agenda planning
- `meeting_minutes` and `topics_list` for captured minutes and topics discussed
- `actions_list` for follow-up actions, owners, and approval state

The data model originated from a Power Platform solution export, allowing existing meeting governance concepts to be retained while the application runs independently in Python.

## Solution Import

Place a compatible Power Platform solution zip in `data/import`, then validate and unpack it:

```powershell
python scripts/unpack_solution.py data/import/solution.zip
```

The importer rejects invalid archives, symbolic links, and unsafe extraction paths. After unpacking, create or verify the SQLite schema:

```powershell
python scripts/import_dataverse_schema.py
```

The schema importer retains the exported structure but removes the source publisher prefix from table and column names. It is configuration-driven through `PPM_SOLUTION_EXPORT_DIRECTORY`.

## Development

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
pytest
```

## Layout

- `app/api`: HTTP endpoints
- `app/ui`: NiceGUI pages
- `app/models`: imported Dataverse schema metadata and shared domain values
- `app/services`: meeting, topic, minutes, and action workflows
- `app/workflows`: background reminder and flow jobs
- `app/config`: environment-backed settings
- `migrations`: Alembic environment and revisions
- `scripts`: solution validation and schema-import utilities
- `tests`: automated tests
- `data`: local SQLite database, solution archives, and unpacked exports
