"""
config.py
---------
Centralized configuration loader for the LinkedIn Content Agent.
"""

import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")

LINKEDIN_EMAIL: str | None = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD: str | None = os.getenv("LINKEDIN_PASSWORD")
LINKEDIN_PROFILE_URL: str | None = os.getenv("LINKEDIN_PROFILE_URL")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_POSTS_PATH = os.path.join(DATA_DIR, "raw_posts.json")
SAMPLE_POSTS_PATH = os.path.join(DATA_DIR, "sample_posts.json")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

GEMINI_CHAT_MODEL = "gemini-2.5-flash"
GEMINI_EMBEDDING_MODEL = "models/gemini-embedding-001"
CHROMA_COLLECTION_NAME = "style_reference_posts"

# How many past posts to retrieve as style examples per generation.
DEFAULT_RETRIEVAL_K = 4


def require_keys(*keys: str) -> None:
    """Raise a clear, actionable error if required env vars are missing.

    Args:
        *keys: Names of the variables (as defined in this module) to check,
            e.g. require_keys("GEMINI_API_KEY", "TAVILY_API_KEY").

    Raises:
        EnvironmentError: If any of the requested keys is missing or empty.
    """
    missing = [k for k in keys if not globals().get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Add them to a .env file in the project root (see .env.example)."
        )
