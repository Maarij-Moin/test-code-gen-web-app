"""Async CRUD helpers for database-backed platform entities."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import GeneratedTest, Job, Repository, User, ValidationRun, WebhookEvent

ModelT = TypeVar("ModelT")


async def commit_and_refresh(session: AsyncSession, instance: ModelT) -> ModelT:
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance


async def get_by_id(session: AsyncSession, model: type[ModelT], id_: uuid.UUID) -> ModelT | None:
    return await session.get(model, id_)


async def list_with_pagination(
    session: AsyncSession,
    stmt: Select[tuple[ModelT]],
    *,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[ModelT]:
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


async def count_for_statement(session: AsyncSession, stmt: Select[Any]) -> int:
    count_stmt = select(func.count()).select_from(stmt.subquery())
    result = await session.execute(count_stmt)
    return int(result.scalar_one())


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    hashed_password: str,
    full_name: str | None = None,
    is_superuser: bool = False,
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hashed_password,
        full_name=full_name,
        is_superuser=is_superuser,
    )
    return await commit_and_refresh(session, user)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(func.lower(User.email) == email.lower()))
    return result.scalar_one_or_none()


async def create_repository(
    session: AsyncSession,
    *,
    name: str,
    repo_url: str,
    owner_id: uuid.UUID | None = None,
    provider: str = "github",
    default_branch: str = "main",
    local_path: str | None = None,
    vector_repo_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Repository:
    repository = Repository(
        name=name,
        repo_url=repo_url,
        owner_id=owner_id,
        provider=provider,
        default_branch=default_branch,
        local_path=local_path,
        vector_repo_id=vector_repo_id,
        metadata_=metadata or {},
    )
    return await commit_and_refresh(session, repository)


async def get_repository_by_url(session: AsyncSession, repo_url: str) -> Repository | None:
    result = await session.execute(select(Repository).where(Repository.repo_url == repo_url))
    return result.scalar_one_or_none()


async def list_repositories(
    session: AsyncSession,
    *,
    owner_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Repository]:
    stmt = select(Repository).order_by(Repository.created_at.desc())
    if owner_id:
        stmt = stmt.where(Repository.owner_id == owner_id)
    return await list_with_pagination(session, stmt, limit=limit, offset=offset)


async def create_job(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID,
    job_type: str,
    status: str = "queued",
    created_by_id: uuid.UUID | None = None,
    webhook_event_id: uuid.UUID | None = None,
    commit_sha: str | None = None,
    branch: str | None = None,
    celery_task_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        repo_id=repo_id,
        created_by_id=created_by_id,
        webhook_event_id=webhook_event_id,
        job_type=job_type,
        status=status,
        commit_sha=commit_sha,
        branch=branch,
        celery_task_id=celery_task_id,
        payload=payload or {},
    )
    return await commit_and_refresh(session, job)


async def get_job_with_children(session: AsyncSession, job_id: uuid.UUID) -> Job | None:
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.generated_tests), selectinload(Job.validation_runs))
        .where(Job.id == job_id)
    )
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID | None = None,
    status: str | None = None,
    job_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if repo_id:
        stmt = stmt.where(Job.repo_id == repo_id)
    if status:
        stmt = stmt.where(Job.status == status)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    return await list_with_pagination(session, stmt, limit=limit, offset=offset)


async def update_job_status(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    status: str,
    error_message: str | None = None,
    payload_patch: dict[str, Any] | None = None,
) -> Job | None:
    job = await session.get(Job, job_id)
    if not job:
        return None
    job.status = status
    job.error_message = error_message
    if payload_patch:
        job.payload = {**(job.payload or {}), **payload_patch}
    return await commit_and_refresh(session, job)


async def create_generated_test(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    repo_id: uuid.UUID,
    file_path: str,
    content: str,
    test_file_path: str | None = None,
    function_name: str | None = None,
    framework: str | None = None,
    language: str | None = None,
    prompt: str | None = None,
    old_code: str | None = None,
    new_code: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> GeneratedTest:
    generated_test = GeneratedTest(
        job_id=job_id,
        repo_id=repo_id,
        file_path=file_path,
        test_file_path=test_file_path,
        function_name=function_name,
        framework=framework,
        language=language,
        content=content,
        prompt=prompt,
        old_code=old_code,
        new_code=new_code,
        metadata_=metadata or {},
    )
    return await commit_and_refresh(session, generated_test)


async def create_webhook_event(
    session: AsyncSession,
    *,
    event_type: str,
    provider: str = "github",
    repo_id: uuid.UUID | None = None,
    delivery_id: str | None = None,
    signature: str | None = None,
    status: str = "received",
    commit_sha: str | None = None,
    branch: str | None = None,
    payload: dict[str, Any] | None = None,
) -> WebhookEvent:
    event = WebhookEvent(
        repo_id=repo_id,
        provider=provider,
        event_type=event_type,
        delivery_id=delivery_id,
        signature=signature,
        status=status,
        commit_sha=commit_sha,
        branch=branch,
        payload=payload or {},
    )
    return await commit_and_refresh(session, event)


async def create_validation_run(
    session: AsyncSession,
    *,
    repo_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    generated_test_id: uuid.UUID | None = None,
    status: str = "queued",
    command: str | None = None,
    exit_code: int | None = None,
    attempts: int = 0,
    passed: bool = False,
    repaired: bool = False,
    stdout: str | None = None,
    stderr: str | None = None,
    report: dict[str, Any] | None = None,
) -> ValidationRun:
    validation_run = ValidationRun(
        repo_id=repo_id,
        job_id=job_id,
        generated_test_id=generated_test_id,
        status=status,
        command=command,
        exit_code=exit_code,
        attempts=attempts,
        passed=passed,
        repaired=repaired,
        stdout=stdout,
        stderr=stderr,
        report=report or {},
    )
    return await commit_and_refresh(session, validation_run)
