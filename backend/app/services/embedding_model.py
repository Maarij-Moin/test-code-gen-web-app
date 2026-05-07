import logging
import threading
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model — singleton (loaded once, reused across all calls)
# ---------------------------------------------------------------------------
_embeddings_instance: FastEmbedEmbeddings | None = None
_embeddings_lock = threading.Lock()

def _get_embeddings() -> FastEmbedEmbeddings:
    """Return the shared embedding model, loading it on first call only.

    Thread-safe singleton: FastEmbed is efficient and uses ONNX Runtime.
    Reusing a single instance avoids redundant memory allocation.
    """
    global _embeddings_instance
    if _embeddings_instance is None:
        with _embeddings_lock:
            if _embeddings_instance is None:  # double-checked locking
                logger.info("Loading FastEmbed model (first call)...")
                _embeddings_instance = FastEmbedEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5"
                )
                logger.info("FastEmbed model loaded.")
    return _embeddings_instance
