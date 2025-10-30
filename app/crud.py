from typing import List, Optional

from sqlalchemy.orm import Session

from . import models, schemas


def create_log_entry(db: Session, payload: schemas.LogEntryCreate) -> models.LogEntry:
    """Persist a new log entry."""
    entry = models.LogEntry(
        key=payload.key,
        name=payload.name,
        text=payload.text,
        payload=payload.payload,
        duration_ms=payload.duration_ms,
        observed_at=payload.observed_at,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_log_entries(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
    key: Optional[str] = None,
    name: Optional[str] = None,
) -> List[models.LogEntry]:
    """Return recent log entries filtered by optional key or name."""
    query = db.query(models.LogEntry)
    if key:
        query = query.filter(models.LogEntry.key == key)
    if name:
        query = query.filter(models.LogEntry.name == name)
    return (
        query.order_by(models.LogEntry.created_at.desc())
        .offset(skip)
        .limit(min(limit, 500))
        .all()
    )
