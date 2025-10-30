from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    text = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"LogEntry(id={self.id!r}, key={self.key!r}, name={self.name!r}, "
            f"created_at={self.created_at!r})"
        )
