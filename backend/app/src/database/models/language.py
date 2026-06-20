from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.src.database.models.dataset import Dataset
    from app.src.database.models.research import Research


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class Language(SQLModel, table=True):
    __tablename__ = "languages"

    id: str = Field(default_factory=lambda: new_id("lang"), primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    name: str = Field(index=True, max_length=160)
    details: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON, nullable=False))
    created_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=now_utc, sa_column=Column(DateTime(timezone=True), nullable=False))

    datasets: list["Dataset"] = Relationship(
        back_populates="language",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    research: list["Research"] = Relationship(
        back_populates="language",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
