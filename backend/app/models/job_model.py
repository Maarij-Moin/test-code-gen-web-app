"""
Ingestion Job ORM model — SQLite-compatible (AuthBase).

This model tracks the lifecycle of an async repo ingestion job:
    PENDING  → CLONING → INDEXING → COMPLETED
                                  ↘ FAILED

It intentionally re-uses the lightweight AuthBase declarative base that is
backed by SQLite so that the table is created at startup via
``init_auth_db()`` without requiring Alembic migrations.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.user_model import AuthBase


class JobStatus(str, enum.Enum):
    """Ordered pipeline lifecycle statuses."""

    PENDING = "PENDING"
    CLONING = "CLONING"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionJob(AuthBase):
    """Tracks a single async clone-and-index pipeline run."""

    __tablename__ = "ingestion_jobs"

    # Primary key — plain string UUID for SQLite portability
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # The URL that was submitted
    repo_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Derived repo name extracted from URL
    repo_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Filesystem path where the repo was cloned
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Stable Chroma repo identifier returned by make_repo_id()
    vector_repo_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Pipeline phase
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=JobStatus.PENDING.value,
    )

    # Human-readable progress detail visible to the poller
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full structured error captured on FAILED
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Wallclock timestamps for each phase boundary
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cloning_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    indexing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_ingestion_jobs_status", "status"),
        Index("ix_ingestion_jobs_repo_url", "repo_url"),
        Index("ix_ingestion_jobs_created_at", "created_at"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<IngestionJob id={self.id} status={self.status} repo_url={self.repo_url!r}>"
