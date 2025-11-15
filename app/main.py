from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas
from .batcher import LogBatcher
from .config import settings
from .database import close_db, get_session, init_db
from .utils import normalize_workspace_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log_batcher.start()
    yield
    await log_batcher.stop()
    await close_db()


app = FastAPI(title="Orbital Log", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LimitQuery = Annotated[
    int,
    Query(
        ge=1,
        le=settings.max_page_size,
        description="Maximum number of log entries to return",
        example=50,
    ),
]
OffsetQuery = Annotated[int, Query(ge=0)]

log_batcher = LogBatcher(max_batch_size=10, flush_interval=0.150)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/workspaces/{workspace_id}/logs",
    response_model=schemas.LogRead,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_log(
    workspace_id: str,
    payload: schemas.LogCreate,
) -> schemas.LogRead:
    workspace_id = normalize_workspace_id(workspace_id)
    entry = await log_batcher.enqueue(
        workspace_id=workspace_id,
        message=payload.message,
        code=payload.code,
        meta=payload.meta,
    )
    return entry


@app.get("/workspaces/{workspace_id}/logs", response_model=schemas.LogListResponse)
async def read_logs(
    workspace_id: str,
    limit: LimitQuery = settings.default_page_size,
    offset: OffsetQuery = 0,
    code: int | None = Query(default=None, description="Filter by code bucket (200/300/400/500)"),
    search: str | None = Query(default=None, description="Full text search over message bodies"),
    start: datetime | None = Query(default=None, description="ISO timestamp lower bound"),
    end: datetime | None = Query(default=None, description="ISO timestamp upper bound"),
    session: AsyncSession = Depends(get_session),
) -> schemas.LogListResponse:
    workspace_id = normalize_workspace_id(workspace_id)
    if code is not None and code not in settings.allowed_status_codes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"code must be one of {settings.allowed_status_codes}",
        )
    stmt = select(models.LogEntry).where(models.LogEntry.workspace_id == workspace_id)
    count_stmt: Select[int] = select(func.count()).select_from(models.LogEntry).where(
        models.LogEntry.workspace_id == workspace_id
    )
    stmt, count_stmt = _apply_common_filters(stmt, count_stmt, code=code, search=search, start=start, end=end)
    stmt = stmt.order_by(models.LogEntry.created_at.desc()).offset(offset).limit(limit)

    result = await session.execute(stmt)
    entries = result.scalars().all()

    total = await session.scalar(count_stmt) or 0

    return schemas.LogListResponse(items=entries, total=total, limit=limit, offset=offset)


@app.get(
    "/workspaces/{workspace_id}/stats",
    response_model=schemas.WorkspaceStats,
)
async def workspace_stats(
    workspace_id: str,
    session: AsyncSession = Depends(get_session),
) -> schemas.WorkspaceStats:
    workspace_id = normalize_workspace_id(workspace_id)
    stmt = (
        select(models.LogEntry.code, func.count())
        .where(models.LogEntry.workspace_id == workspace_id)
        .group_by(models.LogEntry.code)
    )
    rows = await session.execute(stmt)
    counts = {code: count for code, count in rows.all()}
    ordered = [schemas.CodeCount(code=code, count=counts.get(code, 0)) for code in settings.allowed_status_codes]
    total = sum(item.count for item in ordered)
    return schemas.WorkspaceStats(workspace_id=workspace_id, totals=ordered, total_events=total)


@app.get("/stats/codes", response_model=schemas.GlobalStats)
async def global_code_stats(session: AsyncSession = Depends(get_session)) -> schemas.GlobalStats:
    stmt = select(models.LogEntry.code, func.count()).group_by(models.LogEntry.code)
    rows = await session.execute(stmt)
    counts = {code: count for code, count in rows.all()}

    workspace_stmt = select(func.count(func.distinct(models.LogEntry.workspace_id)))
    distinct_workspaces = await session.scalar(workspace_stmt) or 0

    ordered = [schemas.CodeCount(code=code, count=counts.get(code, 0)) for code in settings.allowed_status_codes]
    total = sum(item.count for item in ordered)
    return schemas.GlobalStats(totals=ordered, distinct_workspaces=distinct_workspaces, total_events=total)


def _apply_common_filters(
    stmt: Select[models.LogEntry],
    count_stmt: Select[int],
    *,
    code: int | None,
    search: str | None,
    start: datetime | None,
    end: datetime | None,
) -> tuple[Select[models.LogEntry], Select[int]]:
    if code is not None:
        stmt = stmt.where(models.LogEntry.code == code)
        count_stmt = count_stmt.where(models.LogEntry.code == code)
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(models.LogEntry.message.ilike(pattern))
        count_stmt = count_stmt.where(models.LogEntry.message.ilike(pattern))
    if start:
        stmt = stmt.where(models.LogEntry.created_at >= start)
        count_stmt = count_stmt.where(models.LogEntry.created_at >= start)
    if end:
        stmt = stmt.where(models.LogEntry.created_at <= end)
        count_stmt = count_stmt.where(models.LogEntry.created_at <= end)
    return stmt, count_stmt
