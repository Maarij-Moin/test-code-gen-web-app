"""
Facade module to maintain backward compatibility with FastAPI routes.
This module re-exports the main services which have been refactored
into smaller modules with clear separation of concerns.
"""

from app.services.embedding_model import _get_embeddings
from app.services.vectorstore_service import make_repo_id, load_vectorstore, delete_chunks_for_file
from app.services.chunking_service import _chunk_by_units, _extract_python_units, _split_by_declarations, _sub_chunk
from app.services.language_config import EXTENSION_MAP, GENERIC_EXTENSION_MAP
from app.services.indexing_service import process_and_store_codebase, process_changed_files, update_vectorstore
from app.services.retrieval_service import retrieve_related_chunks, generate_test_prompt_from_diff, run_diff_pipeline

__all__ = [
    "make_repo_id",
    "load_vectorstore",
    "delete_chunks_for_file",
    "EXTENSION_MAP",
    "GENERIC_EXTENSION_MAP",
    "process_and_store_codebase",
    "process_changed_files",
    "update_vectorstore",
    "retrieve_related_chunks",
    "generate_test_prompt_from_diff",
    "run_diff_pipeline",
]