"""Pydantic schemas for semantic search endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request payload for a semantic query."""

    repo_id: str = Field(..., min_length=1, description="Repository identifier.")
    query: str = Field(..., min_length=1, description="Search query string.")
    k: int = Field(5, ge=1, le=50, description="Number of results to return.")

    class Config:
        json_schema_extra = {
            "example": {
                "repo_id": "repo_7c867f35d4e397a2",
                "query": "Where is the diff pipeline implemented?",
                "k": 5,
            }
        }


class QueryResult(BaseModel):
    """Single semantic search result."""

    content: str = Field(..., description="Matched document content.")
    metadata: dict = Field(..., description="Metadata associated with the content.")
    score: float | None = Field(
        default=None, description="Similarity score (when available)."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content": "def run_diff_pipeline(repo_path: str, ...):",
                "metadata": {"file_path": "app/services/diff_pipeline_service.py"},
                "score": 0.91,
            }
        }


class QueryResponse(BaseModel):
    """Response payload for semantic search results."""

    success: bool = Field(..., description="Whether the query succeeded.")
    total_results: int = Field(..., ge=0, description="Number of results returned.")
    results: list[QueryResult] = Field(
        default_factory=list, description="List of query results."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_results": 2,
                "results": [
                    {
                        "content": "def run_diff_pipeline(...):",
                        "metadata": {"file_path": "app/services/diff_pipeline_service.py"},
                        "score": 0.91,
                    }
                ],
            }
        }

# Future hybrid search expansion: add fields for keyword scoring or rerank data.
