# Orbital Log

Orbital Log is a lightweight FastAPI + PostgreSQL service for recording backend operations. Each log entry is stored with a key, a human-friendly name, optional free-form text, and structured JSON payloads so you can capture context such as queries, timings, request metadata, and more. A bundled single-page frontend lets you submit new entries and browse existing ones without extra tooling.

## Features

- FastAPI backend with SQLAlchemy models stored in PostgreSQL.
- JSON payload support (PostgreSQL `JSONB`) for arbitrary structured data.
- REST endpoints to create and list log entries with filtering by key or name.
- Minimal HTML/JS frontend for submitting logs and viewing recent activity.

## Prerequisites

- Python 3.10 or newer.
- PostgreSQL 13+ (local install or container).
- (Optional) [uvicorn](https://www.uvicorn.org/) for development server.

## Quickstart

1. **Clone and install dependencies**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL**

   If you do not have PostgreSQL installed locally, you can run it via Docker:

   ```bash
   docker run --name orbitallog-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=orbitallog -p 5432:5432 -d postgres:15
   ```

3. **Configure the database URL**

   FastAPI reads `DATABASE_URL` and automatically loads `.env` from the project root. Either edit `.env` or export the variable before running the app:

   ```bash
   set DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/orbitallog  # PowerShell
   ```

4. **Run the server**

   ```bash
   uvicorn app.main:app --reload
   ```

   Visit `http://localhost:8000` for the frontend and `http://localhost:8000/docs` for the interactive OpenAPI docs.

## API Overview

### Create a log entry

```http
POST /api/logs
Content-Type: application/json

{
  "key": "db.query.users",
  "name": "Fetch user list",
  "text": "Retrieved active users for dashboard",
  "payload": {
    "query": "select * from users",
    "time": "1592 ms"
  },
  "duration_ms": 1592
}
```

### List logs

```http
GET /api/logs?key=db.query.users
```

Returns recent entries in descending order by creation time.

## Project Structure

```
app/
├── crud.py          # Database helpers
├── database.py      # Engine & session management
├── main.py          # FastAPI application
├── models.py        # SQLAlchemy models
├── schemas.py       # Pydantic models
├── static/          # Frontend assets
└── templates/       # Jinja2 templates
```

## Development Notes

- Tables are auto-created on start-up if they do not exist.
- The frontend uses the REST API; you can easily swap it for another UI or integrate with other services.
- Add authentication, retention policies, or alerting hooks as your logging needs grow.

## Cleanup

To stop the Docker database (if you used it):

```bash
docker stop orbitallog-db && docker rm orbitallog-db
```
