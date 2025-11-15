from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, validator

from .config import settings

_ALLOWED_CODES = set(settings.allowed_status_codes)


class LogBase(BaseModel):
    message: str = Field(min_length=1, max_length=settings.max_message_length)
    code: int
    meta: dict[str, Any] | None = Field(default=None, description="Optional structured metadata")

    @validator("code")
    def validate_code(cls, value: int) -> int:
        if value not in _ALLOWED_CODES:
            raise ValueError(f"code must be one of {_ALLOWED_CODES}")
        return value


class LogCreate(LogBase):
    pass


class LogRead(LogBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: str
    created_at: datetime


class LogListResponse(BaseModel):
    items: list[LogRead]
    total: int
    limit: int
    offset: int


class CodeCount(BaseModel):
    code: int
    count: int


class WorkspaceStats(BaseModel):
    workspace_id: str
    totals: list[CodeCount]
    total_events: int


class GlobalStats(BaseModel):
    totals: list[CodeCount]
    distinct_workspaces: int
    total_events: int
