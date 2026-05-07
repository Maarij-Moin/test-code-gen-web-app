"""initial database layer

Revision ID: 20260507_0001
Revises:
Create Date: 2026-05-07 00:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260507_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index("ix_users_created_at", "users", ["created_at"], unique=False)
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "repositories",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("repo_url", sa.String(length=1000), nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="github", nullable=False),
        sa.Column("default_branch", sa.String(length=255), server_default="main", nullable=False),
        sa.Column("local_path", sa.String(length=1000), nullable=True),
        sa.Column("vector_repo_id", sa.String(length=128), nullable=True),
        sa.Column("installation_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_repositories_owner_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_repositories")),
        sa.UniqueConstraint("repo_url", name="uq_repositories_repo_url"),
    )
    op.create_index("ix_repositories_created_at", "repositories", ["created_at"], unique=False)
    op.create_index("ix_repositories_owner_id", "repositories", ["owner_id"], unique=False)
    op.create_index("ix_repositories_provider", "repositories", ["provider"], unique=False)
    op.create_index("ix_repositories_vector_repo_id", "repositories", ["vector_repo_id"], unique=False)

    op.create_table(
        "webhook_events",
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=50), server_default="github", nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("delivery_id", sa.String(length=255), nullable=True),
        sa.Column("signature", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="received", nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], name=op.f("fk_webhook_events_repo_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_events_provider_delivery_id"),
    )
    op.create_index("ix_webhook_events_created_at", "webhook_events", ["created_at"], unique=False)
    op.create_index("ix_webhook_events_event_type", "webhook_events", ["event_type"], unique=False)
    op.create_index("ix_webhook_events_repo_id", "webhook_events", ["repo_id"], unique=False)
    op.create_index("ix_webhook_events_status", "webhook_events", ["status"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("webhook_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_jobs_created_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], name=op.f("fk_jobs_repo_id_repositories"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["webhook_event_id"], ["webhook_events.id"], name=op.f("fk_jobs_webhook_event_id_webhook_events"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_celery_task_id", "jobs", ["celery_task_id"], unique=False)
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"], unique=False)
    op.create_index("ix_jobs_repo_status", "jobs", ["repo_id", "status"], unique=False)
    op.create_index("ix_jobs_repo_type_commit", "jobs", ["repo_id", "job_type", "commit_sha"], unique=False)

    op.create_table(
        "generated_tests",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("test_file_path", sa.String(length=1000), nullable=True),
        sa.Column("function_name", sa.String(length=255), nullable=True),
        sa.Column("framework", sa.String(length=100), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("old_code", sa.Text(), nullable=True),
        sa.Column("new_code", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="generated", nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_generated_tests_job_id_jobs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], name=op.f("fk_generated_tests_repo_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_tests")),
    )
    op.create_index("ix_generated_tests_file_path", "generated_tests", ["file_path"], unique=False)
    op.create_index("ix_generated_tests_job_id", "generated_tests", ["job_id"], unique=False)
    op.create_index("ix_generated_tests_repo_status", "generated_tests", ["repo_id", "status"], unique=False)

    op.create_table(
        "validation_runs",
        sa.Column("repo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("generated_test_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("passed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("repaired", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generated_test_id"], ["generated_tests.id"], name=op.f("fk_validation_runs_generated_test_id_generated_tests"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_validation_runs_job_id_jobs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], name=op.f("fk_validation_runs_repo_id_repositories"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_validation_runs")),
    )
    op.create_index("ix_validation_runs_created_at", "validation_runs", ["created_at"], unique=False)
    op.create_index("ix_validation_runs_generated_test_id", "validation_runs", ["generated_test_id"], unique=False)
    op.create_index("ix_validation_runs_job_id", "validation_runs", ["job_id"], unique=False)
    op.create_index("ix_validation_runs_repo_status", "validation_runs", ["repo_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_validation_runs_repo_status", table_name="validation_runs")
    op.drop_index("ix_validation_runs_job_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_generated_test_id", table_name="validation_runs")
    op.drop_index("ix_validation_runs_created_at", table_name="validation_runs")
    op.drop_table("validation_runs")

    op.drop_index("ix_generated_tests_repo_status", table_name="generated_tests")
    op.drop_index("ix_generated_tests_job_id", table_name="generated_tests")
    op.drop_index("ix_generated_tests_file_path", table_name="generated_tests")
    op.drop_table("generated_tests")

    op.drop_index("ix_jobs_repo_type_commit", table_name="jobs")
    op.drop_index("ix_jobs_repo_status", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_celery_task_id", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_webhook_events_status", table_name="webhook_events")
    op.drop_index("ix_webhook_events_repo_id", table_name="webhook_events")
    op.drop_index("ix_webhook_events_event_type", table_name="webhook_events")
    op.drop_index("ix_webhook_events_created_at", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_repositories_vector_repo_id", table_name="repositories")
    op.drop_index("ix_repositories_provider", table_name="repositories")
    op.drop_index("ix_repositories_owner_id", table_name="repositories")
    op.drop_index("ix_repositories_created_at", table_name="repositories")
    op.drop_table("repositories")

    op.drop_index("ix_users_email_lower", table_name="users")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_table("users")
