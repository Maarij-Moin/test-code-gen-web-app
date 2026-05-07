import os
import hashlib
import logging
from langchain_community.vectorstores import Chroma

from app.services.embedding_model import _get_embeddings

logger = logging.getLogger(__name__)

# Base directory where all per-repo Chroma DBs are stored
CHROMA_BASE_DIR = "./chroma_polyglot_storage"

def make_repo_id(repo_path: str) -> str:
    """Return a stable, filesystem-safe ID derived from the canonical repo path.

    Using a SHA-256 hash of the absolute path guarantees:
    - The same path always produces the same ID (deterministic)
    - Different paths never collide
    - The ID is safe to use as a directory name and Chroma collection name
    """
    canonical = os.path.realpath(repo_path)
    return "repo_" + hashlib.sha256(canonical.encode()).hexdigest()[:16]

def load_vectorstore(repo_id: str) -> Chroma:
    """Re-open an existing per-repo Chroma collection by its repo_id.

    Use this to query a repo that was already processed and persisted.
    Raises FileNotFoundError if the repo_id has never been processed.
    """
    persist_dir = os.path.join(CHROMA_BASE_DIR, repo_id)
    if not os.path.isdir(persist_dir):
        raise FileNotFoundError(
            f"No persisted DB found for repo_id '{repo_id}'. "
            "Run process_and_store_codebase() first."
        )
    return Chroma(
        collection_name=repo_id,
        embedding_function=_get_embeddings(),
        persist_directory=persist_dir,
    )

def delete_chunks_for_file(file_path: str, vectorstore) -> int:
    """Delete every embedding chunk whose ``file_path`` metadata matches *file_path*.

    Args:
        file_path:   Absolute path of the file whose chunks should be removed.
        vectorstore: Open Chroma collection for the repo.

    Returns:
        Number of chunks deleted (0 if none found or on error).
    """
    try:
        results = vectorstore.get(where={"file_path": file_path})
        ids_to_delete = results.get("ids", [])
        if ids_to_delete:
            vectorstore.delete(ids=ids_to_delete)
            logger.info("[delete_chunks_for_file] Deleted %d chunk(s) for %s",
                        len(ids_to_delete), file_path)
        return len(ids_to_delete)
    except Exception as e:
        logger.warning("[delete_chunks_for_file] Error deleting chunks for %s: %s",
                       file_path, e)
        return 0
