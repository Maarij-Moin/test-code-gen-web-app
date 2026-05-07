-- =============================================================================
-- PostgreSQL init script — runs once on first container start
-- Add additional DDL / seed data here as needed.
-- The main schema is managed by Alembic migrations.
-- =============================================================================

-- Ensure the database exists (Compose creates it, this is a safety check)
SELECT 'Autonomous AI Testing Platform database initialized' AS status;
