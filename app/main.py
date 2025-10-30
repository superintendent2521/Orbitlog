import logging
import os
import time
from typing import List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from . import crud, models, schemas
from .database import engine, get_db

APP_TITLE = "Orbital Log"

app = FastAPI(title=APP_TITLE, version="0.1.0")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def ensure_tables() -> None:
    """Create database tables with basic retry so startup waits for the DB."""
    retries = int(os.getenv("DB_STARTUP_RETRIES", "5"))
    delay = float(os.getenv("DB_STARTUP_DELAY", "2.0"))
    for attempt in range(1, retries + 1):
        try:
            models.Base.metadata.create_all(bind=engine)
            return
        except OperationalError as exc:
            logging.warning(
                "Database connection failed (attempt %s/%s): %s", attempt, retries, exc
            )
            if attempt == retries:
                raise
            time.sleep(delay)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Serve the lightweight frontend."""
    return templates.TemplateResponse("index.html", {"request": request, "title": APP_TITLE})


@app.post("/api/logs", response_model=schemas.LogEntryRead, status_code=201)
def create_log_entry(
    payload: schemas.LogEntryCreate, db: Session = Depends(get_db)
) -> schemas.LogEntryRead:
    """Create a log entry."""
    return crud.create_log_entry(db, payload)


@app.get("/api/logs", response_model=List[schemas.LogEntryRead])
def list_log_entries(
    *,
    key: Optional[str] = Query(default=None, description="Filter by key"),
    name: Optional[str] = Query(default=None, description="Filter by name"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[schemas.LogEntryRead]:
    """List log entries with optional filtering."""
    return crud.list_log_entries(db, skip=skip, limit=limit, key=key, name=name)
