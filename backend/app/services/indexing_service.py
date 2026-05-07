import os
import hashlib
import logging
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from app.services.diff_service import get_changed_files
from app.services.embedding_model import _get_embeddings
from app.services.vectorstore_service import CHROMA_BASE_DIR, make_repo_id, load_vectorstore, delete_chunks_for_file
from app.services.language_config import EXTENSION_MAP, GENERIC_EXTENSION_MAP
from app.services.chunking_service import _chunk_by_units

logger = logging.getLogger(__name__)

def process_and_store_codebase(repo_path: str) -> tuple[Chroma, str]:
    """Chunk, embed, and persist an entire codebase.

    Each repo gets its own isolated Chroma collection + subdirectory so that
    multiple users / repos never share or pollute each other's data.

    Returns:
        (vectorstore, repo_id) — callers should store repo_id so they can
        reload or query the correct collection later via load_vectorstore().
    """
    # ------------------------------------------------------------------ #
    # Derive a stable, unique ID from the repo path                       #
    # ------------------------------------------------------------------ #
    repo_id = make_repo_id(repo_path)
    persist_dir = os.path.join(CHROMA_BASE_DIR, repo_id)
    os.makedirs(persist_dir, exist_ok=True)

    logger.info("[process_and_store_codebase] repo_id=%s  persist_dir=%s", repo_id, persist_dir)

    embeddings = _get_embeddings()
    vectorstore = Chroma(
        collection_name=repo_id,          # ← isolated per repo
        embedding_function=embeddings,
        persist_directory=persist_dir,    # ← isolated subdirectory
    )

    documents = []
    ids       = []
    skipped = 0

    for root, _, files in os.walk(repo_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            file_path = os.path.join(root, file)

            # ----------------------------------------------------------------
            # Choose splitter strategy
            # ----------------------------------------------------------------
            if ext in EXTENSION_MAP:
                lang_info = EXTENSION_MAP[ext]
                use_generic = False
            elif ext in GENERIC_EXTENSION_MAP:
                lang_info = GENERIC_EXTENSION_MAP[ext]
                use_generic = True
            else:
                # Unsupported extension — skip silently
                continue

            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                # ---- Function / class -level chunking --------------------
                for chunk_text, unit_meta in _chunk_by_units(
                    content, ext, lang_info, use_generic
                ):
                    # Stable, deterministic ID → Chroma upserts instead of
                    # duplicating on every re-run of the same repo.
                    doc_id = hashlib.md5(
                        (
                            file_path
                            + unit_meta.get("unit_name", "")
                            + str(unit_meta.get("start_line", ""))
                        ).encode()
                    ).hexdigest()

                    doc = Document(
                        page_content=chunk_text,
                        metadata={
                            # --- file-level context ---
                            "file_path":      file_path,
                            "language":       lang_info["name"],
                            "test_framework": lang_info["framework"],
                            "extension":      ext,
                            "is_test_file":   "test" in file_path.lower(),
                            # --- unit-level context (from _chunk_by_units) ---
                            **unit_meta,
                        },
                    )
                    documents.append(doc)
                    ids.append(doc_id)

            except Exception as e:
                logger.warning("[process_and_store_codebase] Skipping '%s': %s", file_path, e)
                skipped += 1

    logger.info(
        "[process_and_store_codebase] %d chunk(s) created across %d supported "
        "extension(s) (%d file(s) skipped). Saving to ChromaDB …",
        len(documents),
        len(EXTENSION_MAP) + len(GENERIC_EXTENSION_MAP),
        skipped,
    )

    if documents:
        # Safe upsert: delete stale entries by ID before re-inserting so that
        # re-running on the same repo never accumulates duplicate vectors.
        try:
            vectorstore.delete(ids=ids)
        except Exception as e:
            logger.debug("delete() before add_documents skipped: %s", e)
        vectorstore.add_documents(documents, ids=ids)

        # Explicitly persist to disk.
        # Chroma >= 0.4.x auto-persists when persist_directory is set, but
        # calling persist() is safe and ensures compatibility with older versions.
        try:
            vectorstore.persist()
            logger.info("[process_and_store_codebase] Vectorstore persisted to disk.")
        except AttributeError:
            # Newer Chroma versions removed the method; auto-persist is active.
            logger.debug(
                "[process_and_store_codebase] Chroma auto-persist active "
                "(persist_directory is set) — no explicit persist() needed."
            )

    logger.info("[process_and_store_codebase] Done. ChromaDB ready. repo_id=%s", repo_id)
    return vectorstore, repo_id


def process_changed_files(repo_path: str) -> list[str]:
    """Return a filtered list of files that changed in the last commit
    AND have a supported extension (EXTENSION_MAP or GENERIC_EXTENSION_MAP).

    Useful for incremental re-indexing: instead of re-processing the entire
    repo, only update the embeddings for files that actually changed.

    Args:
        repo_path: Absolute or relative path to the git repository root.

    Returns:
        List of file paths (strings) that are both changed and supported.
        Returns an empty list if no supported files changed.
    """
    all_supported_exts = set(EXTENSION_MAP.keys()) | set(GENERIC_EXTENSION_MAP.keys())

    changed_files = get_changed_files(repo_path)

    supported_changed = [
        f for f in changed_files
        if f.strip()  # skip empty lines produced by git diff
        and os.path.splitext(f)[1].lower() in all_supported_exts
    ]

    logger.info(
        "[process_changed_files] %d file(s) changed in last commit, "
        "%d with supported extension(s).",
        len(changed_files), len(supported_changed),
    )
    return supported_changed


def update_vectorstore(repo_path: str, repo_id: str) -> tuple[Chroma, int]:
    """Incrementally update embeddings for files changed in the last git commit.

    Only processes files returned by process_changed_files(), making this
    dramatically faster than a full re-index for large repositories.

    Flow per changed file:
        1. Delete existing chunks (by metadata filter on file_path)
        2. Re-chunk the file at function/class level
        3. Compute deterministic IDs
        4. Safe-upsert via delete(ids) + add_documents(ids=ids)

    Args:
        repo_path: Absolute path to the git repository root.
        repo_id:   ID returned by process_and_store_codebase().

    Returns:
        (vectorstore, total_chunks_added)
    """
    vectorstore = load_vectorstore(repo_id)
    changed_files = process_changed_files(repo_path)

    if not changed_files:
        logger.info("[update_vectorstore] No supported files changed. Nothing to do.")
        return vectorstore, 0

    total_added = 0

    for rel_path in changed_files:
        abs_path = os.path.join(repo_path, rel_path)
        ext = os.path.splitext(rel_path)[1].lower()

        if ext in EXTENSION_MAP:
            lang_info = EXTENSION_MAP[ext]
            use_generic = False
        elif ext in GENERIC_EXTENSION_MAP:
            lang_info = GENERIC_EXTENSION_MAP[ext]
            use_generic = True
        else:
            continue

        logger.info("[update_vectorstore] Processing changed file: %s", rel_path)

        # Step 1 — remove all stale chunks for this file
        deleted = delete_chunks_for_file(abs_path, vectorstore)
        logger.info("  Deleted %d stale chunk(s).", deleted)

        # Step 2 — re-chunk and re-embed
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            documents: list[Document] = []
            ids: list[str] = []

            for chunk_text, unit_meta in _chunk_by_units(
                content, ext, lang_info, use_generic
            ):
                doc_id = hashlib.md5(
                    (
                        abs_path
                        + unit_meta.get("unit_name", "")
                        + str(unit_meta.get("start_line", ""))
                    ).encode()
                ).hexdigest()

                doc = Document(
                    page_content=chunk_text,
                    metadata={
                        "file_path":      abs_path,
                        "language":       lang_info["name"],
                        "test_framework": lang_info["framework"],
                        "extension":      ext,
                        "is_test_file":   "test" in rel_path.lower(),
                        **unit_meta,
                    },
                )
                documents.append(doc)
                ids.append(doc_id)

            if documents:
                # Safe upsert
                try:
                    vectorstore.delete(ids=ids)
                except Exception:
                    pass
                vectorstore.add_documents(documents, ids=ids)
                total_added += len(documents)
                logger.info("  Inserted %d chunk(s) for %s.", len(documents), rel_path)

        except Exception as e:
            logger.error("[update_vectorstore] Skipping %s: %s", rel_path, e)

    # Persist
    try:
        vectorstore.persist()
    except AttributeError:
        pass  # Chroma >= 0.4 auto-persists

    logger.info(
        "[update_vectorstore] Done. %d chunk(s) added/updated across %d file(s).",
        total_added, len(changed_files),
    )
    return vectorstore, total_added
