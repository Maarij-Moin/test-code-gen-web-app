import logging
import threading
from langchain_community.embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model — singleton (loaded once, reused across all calls)
# ---------------------------------------------------------------------------
_embeddings_instance: HuggingFaceEmbeddings | None = None
_embeddings_lock = threading.Lock()

def _get_embeddings() -> HuggingFaceEmbeddings:
    """Return the shared embedding model, loading it on first call only.

    Thread-safe singleton: the model is expensive to load (~1-2 s and several
    hundred MB of RAM).  Reusing a single instance avoids that cost on every
    call to process_and_store_codebase() or load_vectorstore().
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        with _embeddings_lock:
            if _embeddings_instance is None:  # double-checked locking
                logger.info("Loading embedding model (first call)...")
                _embeddings_instance = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5",
                    model_kwargs={"device": "cpu"},
                    encode_kwargs={"normalize_embeddings": True},
                )
                logger.info("Embedding model loaded.")
    return _embeddings_instance
