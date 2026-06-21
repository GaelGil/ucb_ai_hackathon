from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.src.database.models.job import JobStatus


class JobCreate(BaseModel):
    type: str
    status: JobStatus = JobStatus.queued
    progress: int = Field(default=0, ge=0, le=100)
    message: str = ""
    error: str | None = None
    job_metadata: dict[str, Any] = {}


class JobUpdate(BaseModel):
    status: JobStatus | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    message: str | None = None
    error: str | None = None
    job_metadata: dict[str, Any] | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    status: JobStatus
    progress: int
    message: str
    error: str | None
    job_metadata: dict[str, Any]
