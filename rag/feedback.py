"""Feedback loop storage and retrieval for thumbs up/down signals."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import chromadb
from sentence_transformers import SentenceTransformer

from config import (
    FEEDBACK_FILE_PATH,
    FEEDBACK_MIN_SIMILARITY,
    FEEDBACK_TOP_K,
    LOCAL_EMBEDDING_MODEL,
    MODEL_CACHE_DIR,
    VECTOR_STORE_PATH,
)

FEEDBACK_POSITIVE_COLLECTION = "dental_boutique_feedback_positive"

_feedback_model: SentenceTransformer | None = None


def _get_feedback_model() -> SentenceTransformer:
    """Lazily load local text embedding model for feedback similarity."""
    global _feedback_model
    if _feedback_model is None:
        _feedback_model = SentenceTransformer(
            LOCAL_EMBEDDING_MODEL,
            cache_folder=MODEL_CACHE_DIR,
        )
    return _feedback_model


def _feedback_file() -> Path:
    path = Path(FEEDBACK_FILE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_feedback_event(event: dict[str, Any]) -> None:
    """Persist raw feedback events for offline analysis."""
    with _feedback_file().open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=True) + "\n")


def _get_positive_collection() -> Any:
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    return client.get_or_create_collection(
        name=FEEDBACK_POSITIVE_COLLECTION,
        metadata={
            "description": "Positive user feedback examples for improved answers",
            "hnsw:space": "cosine",
        },
    )


def record_feedback(
    *,
    question: str,
    answer: str,
    role: str,
    feedback: str,
    images: list[dict[str, Any]] | None = None,
) -> None:
    """Record thumbs feedback; index positive feedback for retrieval-time learning."""
    feedback = feedback.lower().strip()
    if feedback not in {"up", "down"}:
        raise ValueError("feedback must be 'up' or 'down'")

    event = {
        "id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "feedback": feedback,
        "question": question.strip(),
        "answer": answer.strip(),
        "images": images or [],
    }
    _append_feedback_event(event)

    if feedback == "up" and event["question"] and event["answer"]:
        model = _get_feedback_model()
        text = event["question"]
        embedding = model.encode(text, normalize_embeddings=True).tolist()
        collection = _get_positive_collection()
        collection.add(
            ids=[event["id"]],
            embeddings=[embedding],
            metadatas=[
                {
                    "question": event["question"],
                    "answer": event["answer"],
                    "role": event["role"],
                    "timestamp": event["timestamp"],
                }
            ],
            documents=[event["answer"]],
        )


def get_positive_feedback_context(question: str) -> list[dict[str, str]]:
    """
    Return top similar positively-rated Q/A pairs to guide future answers.
    """
    if not question.strip():
        return []
    client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    try:
        collection = client.get_collection(name=FEEDBACK_POSITIVE_COLLECTION)
    except Exception:
        return []

    model = _get_feedback_model()
    query_embedding = model.encode(question, normalize_embeddings=True).tolist()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, FEEDBACK_TOP_K),
        include=["metadatas", "distances"],
    )
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    if not metadatas:
        return []

    examples: list[dict[str, str]] = []
    for meta, distance in zip(metadatas, distances):
        similarity = 1.0 - float(distance)
        if similarity < FEEDBACK_MIN_SIMILARITY:
            continue
        question_text = str(meta.get("question", "")).strip()
        answer_text = str(meta.get("answer", "")).strip()
        if not question_text or not answer_text:
            continue
        examples.append({"question": question_text, "answer": answer_text})
    return examples
