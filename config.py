"""Configuration from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root so it's found regardless of cwd
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

# API keys: use OpenRouter and/or OpenAI (OpenRouter key used for LLM and optionally embeddings)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Vector store: directory for Chroma persistence
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", str(PROJECT_ROOT / "data" / "chroma"))

# Cache dir for local embedding model downloads
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", str(PROJECT_ROOT / "data" / "model_cache"))
os.environ.setdefault("HF_HOME", MODEL_CACHE_DIR)
os.environ.setdefault("TRANSFORMERS_CACHE", MODEL_CACHE_DIR)
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", MODEL_CACHE_DIR)

# Documents to ingest (project root)
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", str(PROJECT_ROOT))

# LLM model (OpenRouter uses provider/model, e.g. openai/gpt-4o)
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o")

# Local embedding model (runs on CPU, no API needed)
LOCAL_EMBEDDING_MODEL = os.getenv("TEXT_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

# Local multimodal model used for image embeddings and image-query matching
IMAGE_EMBEDDING_MODEL = os.getenv(
    "IMAGE_EMBEDDING_MODEL", "sentence-transformers/clip-ViT-B-32"
)

# Directory where extracted doc images are saved for serving via /static
EXTRACTED_IMAGES_DIR = os.getenv(
    "EXTRACTED_IMAGES_DIR",
    str(PROJECT_ROOT / "static" / "indexed_images"),
)

# Feedback storage for thumbs up/down loop
FEEDBACK_FILE_PATH = os.getenv(
    "FEEDBACK_FILE_PATH",
    str(PROJECT_ROOT / "data" / "feedback.jsonl"),
)

# Retrieval
TOP_K = int(os.getenv("TOP_K", "5"))
IMAGE_TOP_K = int(os.getenv("IMAGE_TOP_K", "3"))
IMAGE_MIN_SIMILARITY = float(os.getenv("IMAGE_MIN_SIMILARITY", "0.22"))
FEEDBACK_TOP_K = int(os.getenv("FEEDBACK_TOP_K", "2"))
FEEDBACK_MIN_SIMILARITY = float(os.getenv("FEEDBACK_MIN_SIMILARITY", "0.35"))

# OpenRouter base URL (OpenAI-compatible API)
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


def use_openrouter() -> bool:
    """True if OPENROUTER_API_KEY is set (use OpenRouter for LLM and embeddings)."""
    return bool(OPENROUTER_API_KEY and OPENROUTER_API_KEY.strip())


def get_api_key() -> str:
    """Return the API key to use: OpenRouter if set, else OpenAI."""
    if use_openrouter():
        return OPENROUTER_API_KEY
    if OPENAI_API_KEY and OPENAI_API_KEY.strip():
        return OPENAI_API_KEY
    raise ValueError(
        "Set OPENROUTER_API_KEY or OPENAI_API_KEY in .env (OpenRouter recommended)."
    )


def require_api_key() -> None:
    """Raise if no API key is configured (for RAG operations)."""
    get_api_key()
