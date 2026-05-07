"""Pydantic schemas for diff and test-generation workflows."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiffPipelineRequest(BaseModel):
    """Request payload for diff-driven test generation."""

    repo_path: str = Field(..., min_length=1, description="Local repository path.")
    repo_id: str = Field(..., min_length=1, description="Repository identifier.")

    class Config:
        json_schema_extra = {
            "example": {
                "repo_path": "C:/repos/my-project",
                "repo_id": "repo_7c867f35d4e397a2",
            }
        }


class DiffHunkResponse(BaseModel):
    """Single diff hunk response with generated prompt."""

    file: str = Field(..., description="Relative path to the changed file.")
    function_name: str = Field(..., description="Name of the changed function.")
    old_code: str = Field(..., description="Code removed from the diff.")
    new_code: str = Field(..., description="Code added in the diff.")
    prompt: str = Field(..., description="Generated test prompt for the hunk.")

    class Config:
        json_schema_extra = {
            "example": {
                "file": "src/math_operations.py",
                "function_name": "add",
                "old_code": "return a + b",
                "new_code": "return a + b + 1",
                "prompt": "You are an expert QA engineer...",
            }
        }


class DiffPipelineResponse(BaseModel):
    """Response payload for diff pipeline results."""

    success: bool = Field(..., description="Whether prompt generation succeeded.")
    total_prompts: int = Field(..., ge=0, description="Number of prompts generated.")
    results: list[DiffHunkResponse] = Field(
        default_factory=list, description="Generated prompt results per diff hunk."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "total_prompts": 1,
                "results": [
                    {
                        "file": "src/math_operations.py",
                        "function_name": "add",
                        "old_code": "return a + b",
                        "new_code": "return a + b + 1",
                        "prompt": "You are an expert QA engineer...",
                    }
                ],
            }
        }


class UpdateVectorstoreRequest(BaseModel):
    """Request payload for incremental vectorstore updates."""

    repo_path: str = Field(..., min_length=1, description="Local repository path.")
    repo_id: str = Field(..., min_length=1, description="Repository identifier.")

    class Config:
        json_schema_extra = {
            "example": {
                "repo_path": "C:/repos/my-project",
                "repo_id": "repo_7c867f35d4e397a2",
            }
        }


class UpdateVectorstoreResponse(BaseModel):
    """Response payload for incremental updates."""

    success: bool = Field(..., description="Whether the update succeeded.")
    updated_chunks: int = Field(..., ge=0, description="Number of chunks updated.")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "updated_chunks": 42,
            }
        }
