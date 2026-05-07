"""Pydantic schemas for repository-related API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class RepoUploadRequest(BaseModel):
    """Request payload for cloning a repository."""

    repo_url: HttpUrl = Field(
        ..., description="Git repository URL to clone."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "repo_url": "https://github.com/org/project.git",
            }
        }


class RepoIndexRequest(BaseModel):
    """Request payload for indexing a local repository."""

    repo_path: str = Field(
        ..., min_length=1, description="Absolute path to the local repository."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "repo_path": "C:/repos/my-project",
            }
        }


class CloneAndIndexRequest(BaseModel):
    """Request payload for cloning then indexing a repository."""

    repo_url: HttpUrl = Field(
        ..., description="Git repository URL to clone and index."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "repo_url": "https://github.com/org/project.git",
            }
        }


class RepoResponse(BaseModel):
    """Standard response for repository operations."""

    success: bool = Field(..., description="Whether the request succeeded.")
    message: str = Field(..., description="Human-readable response message.")
    repo_id: str | None = Field(
        default=None, description="Stable repository identifier, when available."
    )
    repo_path: str | None = Field(
        default=None, description="Local path to the repository, when available."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Repository cloned and indexed successfully.",
                "repo_id": "repo_7c867f35d4e397a2",
                "repo_path": "C:/repos/my-project",
            }
        }


class RepoQueryRequest(BaseModel):
    """Request payload for semantic search within a repository."""

    repo_id: str = Field(..., min_length=1, description="Repository identifier.")
    query: str = Field(..., min_length=1, description="Search query text.")
    k: int = Field(5, ge=1, le=50, description="Number of results to return.")

    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "repo_7c867f35d4e397a2",
                "query": "How is the auth middleware configured?",
                "k": 5,
            }
        }
