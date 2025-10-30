from typing import List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, schemas
from .database import engine, get_db

APP_TITLE = "Orbital Log"

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_TITLE, version="0.1.0")

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


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
