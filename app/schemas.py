from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LogEntryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    text: Optional[str] = Field(None, max_length=10_000)
    payload: Optional[Dict[str, Any]] = None
    duration_ms: Optional[int] = Field(None, ge=0)
    observed_at: Optional[datetime] = None

    @field_validator("key", "name")
    def strip_value(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class LogEntryCreate(LogEntryBase):
    pass


class LogEntryRead(LogEntryBase):
    id: int
    created_at: datetime
    updated_at: datetime
