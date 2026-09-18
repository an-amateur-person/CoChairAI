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

## Technology Stack

- **Python 3.12** - Runtime environment
- **FastAPI** - HTTP API framework with automatic documentation
- **NiceGUI** - Web interface (Python-based, no HTML/CSS/JS required)
- **SQLite & SQLAlchemy** - Local persistence and ORM
- **Alembic** - Database schema versioning and migrations
- **APScheduler** - Background job scheduling (reminder scans)
- **pydantic-settings** - Environment-based configuration management
- **pytest** - Automated testing

## Quick Start

### Prerequisites

- Python 3.12 or later

### Setup

```powershell
# Clone or navigate to the project directory
cd cchair-ai

# Create and activate virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
Copy-Item .env.example .env
```

Edit `.env` with your local configuration:
- `CCHAIR_APP_NAME` - Browser and application display name
- `CCHAIR_DATABASE_URL` - SQLAlchemy database connection string
- `CCHAIR_UI_STORAGE_SECRET` - Long random secret for session storage (minimum 16 characters)
- `CCHAIR_SCHEDULER_TIMEZONE` - Timezone for background jobs (e.g., `UTC`, `America/New_York`)
- `CCHAIR_MEETING_TIMEZONE` - Local timezone used for new meeting date and time selections (default: `Europe/Berlin`)
- `CCHAIR_REMINDER_SCAN_INTERVAL_MINUTES` - How often to scan for reminders (default: 15)

### Run the Application

```powershell
uvicorn app.main:app --reload --reload-dir app
```

Open your browser to:
- **UI:** http://127.0.0.1:8000
- **API Documentation:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/api/health

## API Reference

### Health & Status

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Application health check and configured name |

### Meetings

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/meetings` | List all scheduled meetings with topics |
| `POST` | `/api/meetings` | Create a new meeting |
| `POST` | `/api/meetings/{meeting_id}/topics` | Add an agenda topic to a meeting |

### Meeting Minutes & Approvals

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/meeting-minutes/draft` | Create a meeting-minutes draft with topics and actions |
| `POST` | `/api/meetings/{meeting_id}/approve` | Approve meeting minutes and related records |

## Data Model

### Core Tables

- **`meeting`** - Scheduled meeting records with date, duration, attendees, and location
- **`topic_intake`** - Agenda topics with descriptions, duration, and lead assignments
- **`meeting_agendas`** - Mapping between meetings and their agenda topics
- **`meeting_minutes`** - Captured minutes with approval status and timestamps
- **`topics_list`** - Detailed minutes for each topic discussed
- **`actions_list`** - Follow-up action items with owners, status, and due dates

## Development

### Database Migrations

Create a new migration:
```powershell
alembic revision --autogenerate -m "describe your change"
```

Apply migrations:
```powershell
alembic upgrade head
```

### Run Tests

```powershell
pytest
```

Run with verbose output:
```powershell
pytest -v
```

### Project Structure

```
cchair-ai/
├── app/
│   ├── api/              # REST API endpoints and request/response schemas
│   ├── models/           # Database table definitions and enums
│   ├── services/         # Business logic (meeting, topic, minutes operations)
│   ├── ui/               # NiceGUI web interface pages
│   ├── workflows/        # Background job scheduling (reminders)
│   ├── config/           # Environment-based settings
│   ├── main.py           # FastAPI application entry point
│   └── db.py             # Database connection and session management
├── migrations/           # Alembic version control for database schema
├── tests/                # Automated test suite
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project metadata
├── .env.example          # Configuration template
├── .gitignore            # Git ignore patterns
└── README.md             # This file
```

## Configuration Details

### Database

By default, CoChairAI uses SQLite for local development. Configure the database URL in `.env`:

```
CCHAIR_DATABASE_URL=sqlite:///./data/cchair.db
```

For production deployments, you can use other SQLAlchemy-compatible databases (PostgreSQL, MySQL, etc.):

```
CCHAIR_DATABASE_URL=postgresql://user:password@localhost/cchair_db
```

### UI Storage Secret

The NiceGUI framework requires a secure secret for session storage. Generate a strong random string:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Scheduler Configuration

Configure background reminder scans via `.env`:

```
CCHAIR_SCHEDULER_TIMEZONE=America/New_York
CCHAIR_REMINDER_SCAN_INTERVAL_MINUTES=15
```

## Extending the Application

### Adding a New API Endpoint

1. Create a Pydantic schema in `app/api/schemas.py`
2. Add a service method in `app/services/`
3. Add the route in `app/api/router.py`

### Adding a New UI Page

1. Create a page module in `app/ui/`
2. Register it in `app/main.py` after the `register_home_page()` call

### Integrating with External Services

Create a new service module under `app/services/` for each external integration:
- Microsoft Graph (Teams, Outlook)
- SharePoint
- Email notifications
- Copilot or AI services

Keep all credentials and connection details in environment variables, not in source code.

## Troubleshooting

### Database Lock Errors

If you see "database is locked" errors, ensure only one instance of the application is running and close any open database tools.

### Port Already in Use

If port 8000 is in use, specify a different port:

```powershell
uvicorn app.main:app --reload --port 8001
```

### Missing Environment Variables

Ensure all required variables are set in `.env`. Missing non-required variables will use defaults as specified in `app/config/settings.py`.

## Support

For issues, feature requests, or contributions, contact the development team.
