import enum
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, JSON, Text
from sqlmodel import Field, SQLModel

from app.database.models.language import new_id, now_utc


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: str = Field(default_factory=lambda: new_id("job"), primary_key=True)
    type: str = Field(index=True, max_length=120)
    status: JobStatus = Field(default=JobStatus.queued, index=True)
    progress: int = Field(default=0, ge=0, le=100)
    message: str = Field(default="", sa_column=Column(Text, nullable=False))
    error: str | None = Field(default=None, sa_column=Column(Text))
    job_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON, nullable=False))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
