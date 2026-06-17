"""
ingest.py
---------
PART 1 (embedding half) of the style-training pipeline.

WHY THIS FILE EXISTS
We're using RAG instead of fine-tuning to capture Nikit Bassi's writing
style. That means: take his real posts, turn each one into a vector
embedding, and store those vectors so generate_post.py can later retrieve
the most stylistically-relevant examples for any new topic.

This file is the bridge between raw text (data/raw_posts.json or
data/sample_posts.json) and a queryable ChromaDB collection on disk.

HOW IT INTERACTS WITH THE SYSTEM
scrape_posts.py -> raw_posts.json -\
                                     -> ingest.py -> ChromaDB (chroma_db/)
            data/sample_posts.json -/                      |
                                                              v
                                                    generate_post.py reads
                                                    from this same ChromaDB
                                                    collection at query time.
"""

import json
import logging
import os
from typing import Any

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_posts() -> list[dict[str, Any]]:
    """Load posts from raw_posts.json if it exists, else fall back to samples.

    Returns:
        A list of post dicts with at least an "id" and "text" field.

    Raises:
        FileNotFoundError: If neither file exists.
    """
    path = config.RAW_POSTS_PATH if os.path.exists(config.RAW_POSTS_PATH) else config.SAMPLE_POSTS_PATH

    if not os.path.exists(path):
        raise FileNotFoundError(
            "No post data found. Run scrape_posts.py first, or manually "
            "create data/raw_posts.json in the same format as "
            "data/sample_posts.json."
        )

    logger.info("Loading posts from %s", path)
    with open(path, "r", encoding="utf-8") as f:
        posts: list[dict[str, Any]] = json.load(f)

    if not posts:
        raise ValueError(f"{path} exists but contains no posts.")

    return posts


def posts_to_documents(posts: list[dict[str, Any]]) -> list[Document]:
    """Convert raw post dicts into LangChain Document objects.

    Each post becomes a single Document. LinkedIn posts are short enough
    (well under typical embedding token limits) that no chunking is needed —
    chunking a post would actually hurt style retrieval, since it could
    split a hook from its punchline.

    Args:
        posts: Output of load_posts().

    Returns:
        List of Document objects with post text as page_content and
        the post id/topic/likes preserved as metadata.
    """
    documents = []
    for post in posts:
        text = (post.get("text") or "").strip()
        if not text:
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "post_id": post.get("id", "unknown"),
                    "topic": post.get("topic", ""),
                    "likes": post.get("likes", 0),
                },
            )
        )
    return documents


def build_vectorstore(documents: list[Document]) -> Chroma:
    """Embed documents with Gemini and persist them into ChromaDB.

    This rebuilds the collection from scratch each time it's called, which
    keeps ingestion idempotent — re-running ingest.py after adding new posts
    will not create duplicate entries.

    Args:
        documents: Output of posts_to_documents().

    Returns:
        The populated Chroma vectorstore instance.
    """
    config.require_keys("GEMINI_API_KEY")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=config.GEMINI_EMBEDDING_MODEL,
        google_api_key=config.GEMINI_API_KEY,
    )

    # Wipe any existing collection with this name so re-ingestion is clean.
    vectorstore = Chroma(
        collection_name=config.CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=config.CHROMA_DIR,
    )
    existing_ids = vectorstore.get()["ids"]
    if existing_ids:
        vectorstore.delete(ids=existing_ids)
        logger.info("Cleared %d existing vectors before re-ingesting.", len(existing_ids))

    vectorstore.add_documents(documents)
    logger.info("Embedded and stored %d posts in ChromaDB collection '%s'.",
                len(documents), config.CHROMA_COLLECTION_NAME)
    return vectorstore


def main() -> None:
    """CLI entry point: load posts, embed them, persist to ChromaDB."""
    posts = load_posts()
    documents = posts_to_documents(posts)

    if not documents:
        raise ValueError("No valid post text found after cleaning — nothing to embed.")

    build_vectorstore(documents)
    logger.info("Ingestion complete. You can now run app.py.")


if __name__ == "__main__":
    main()
