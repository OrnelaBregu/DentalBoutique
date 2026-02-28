"""Load persisted indexes and run role-aware RAG queries with image retrieval."""
from typing import Any

import chromadb
from llama_index.core import VectorStoreIndex
from llama_index.core.settings import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.llms.openrouter import OpenRouter
from llama_index.vector_stores.chroma import ChromaVectorStore
from sentence_transformers import SentenceTransformer

from config import (
    IMAGE_EMBEDDING_MODEL,
    IMAGE_MIN_SIMILARITY,
    IMAGE_TOP_K,
    get_api_key,
    LOCAL_EMBEDDING_MODEL,
    LLM_MODEL,
    MODEL_CACHE_DIR,
    TOP_K,
    require_api_key,
    use_openrouter,
    VECTOR_STORE_PATH,
)
from rag.feedback import get_positive_feedback_context
from rag.ingestion import IMAGE_COLLECTION_NAME, TEXT_COLLECTION_NAME
from rag.prompts import get_system_prompt

# Lazy-loaded retriever resources
_index: VectorStoreIndex | None = None
_image_collection: Any | None = None
_image_model: SentenceTransformer | None = None
_IMAGE_REQUEST_TERMS = (
    "show",
    "image",
    "images",
    "photo",
    "photos",
    "picture",
    "pictures",
    "xray",
    "x-ray",
    "scan",
    "visual",
)
_TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "dental implant": ("implant", "implants", "implantology"),
    "root canal": ("root canal", "endodontic", "endodontics"),
    "teeth whitening": ("whitening", "bleaching"),
    "invisalign": ("invisalign", "clear aligner", "aligners"),
    "dental crown": ("crown", "crowns"),
    "dental bridge": ("bridge", "bridges"),
    "dental veneers": ("veneer", "veneers"),
    "tooth extraction": ("extraction", "tooth removal", "remove tooth"),
    "dentures": ("denture", "dentures"),
    "teeth cleaning": ("cleaning", "cleanings", "prophylaxis"),
    "dental filling": ("filling", "fillings", "cavity"),
}


def _get_index() -> VectorStoreIndex:
    """Load or create VectorStoreIndex from persisted Chroma."""
    global _index
    if _index is not None:
        return _index
    require_api_key()
    # Local embeddings — same model used during ingestion
    Settings.embed_model = HuggingFaceEmbedding(
        model_name=LOCAL_EMBEDDING_MODEL,
        cache_folder=MODEL_CACHE_DIR,
    )
    # LLM via OpenRouter (or OpenAI)
    if use_openrouter():
        Settings.llm = OpenRouter(model=LLM_MODEL, api_key=get_api_key())
    else:
        Settings.llm = OpenAI(model=LLM_MODEL, api_key=get_api_key())

    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    try:
        chroma_collection = chroma_client.get_collection(name=TEXT_COLLECTION_NAME)
    except Exception:
        raise ValueError(
            "The document index has not been built yet. Run: python -m rag.ingestion"
        )
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    _index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    return _index


def _get_image_collection() -> Any | None:
    """Return image collection if available."""
    global _image_collection
    if _image_collection is not None:
        return _image_collection
    chroma_client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
    try:
        _image_collection = chroma_client.get_collection(name=IMAGE_COLLECTION_NAME)
    except Exception:
        _image_collection = None
    return _image_collection


def _get_image_model() -> SentenceTransformer:
    """Lazily load multimodal embedding model to match text queries to images."""
    global _image_model
    if _image_model is None:
        _image_model = SentenceTransformer(
            IMAGE_EMBEDDING_MODEL,
            cache_folder=MODEL_CACHE_DIR,
        )
    return _image_model


def _retrieve_images(question: str) -> list[dict[str, str]]:
    """Return relevant images for a query based on CLIP similarity."""
    collection = _get_image_collection()
    if collection is None:
        return []
    requested_topic = _requested_topic(question)

    query_embedding = _get_image_model().encode(
        question, normalize_embeddings=True
    ).tolist()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, IMAGE_TOP_K),
        include=["metadatas", "distances"],
    )
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    if not metadatas:
        return []

    images: list[dict[str, str]] = []
    for meta, distance in zip(metadatas, distances):
        if requested_topic:
            stored_topic = str(meta.get("topic_label", "")).strip().lower()
            # Guardrail: if a procedure/topic is requested, require exact topic match.
            if stored_topic != requested_topic:
                continue
        distance_value = float(distance)
        # Chroma returns cosine distance for this collection (1 - cosine similarity).
        similarity = 1.0 - distance_value
        # Fallback if collection was created with L2 distance in an older run.
        if distance_value > 1.0:
            similarity = 1.0 - ((distance_value ** 2) / 2.0)
        min_similarity = IMAGE_MIN_SIMILARITY
        if requested_topic:
            min_similarity = max(IMAGE_MIN_SIMILARITY, 0.30)
        if similarity < min_similarity:
            continue
        url = meta.get("url")
        if not url:
            continue
        images.append(
            {
                "url": str(url),
                "source_doc": str(meta.get("source_doc", "")),
                "image_name": str(meta.get("image_name", "")),
            }
        )
    return images


def _is_explicit_image_request(question: str) -> bool:
    """Return True only when user explicitly asks to see images."""
    lower = question.lower()
    return any(term in lower for term in _IMAGE_REQUEST_TERMS)


def _requested_topic(question: str) -> str | None:
    """Infer requested procedure/topic from query aliases."""
    lower = question.lower()
    for topic, aliases in _TOPIC_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return topic
    return None


def query(question: str, role: str = "patient") -> dict[str, Any]:
    """
    Run a RAG query: retrieve top-k chunks, then generate an answer with role-specific system prompt.
    role: "patient" | "staff"
    """
    index = _get_index()
    retriever = index.as_retriever(similarity_top_k=TOP_K)
    nodes = retriever.retrieve(question)

    # Filter out very low relevance chunks (score below threshold)
    MIN_SCORE = 0.3
    relevant_nodes = [n for n in nodes if n.score is None or n.score >= MIN_SCORE]

    # Guardrail: do not return images unless the user explicitly asks for visuals.
    images = _retrieve_images(question) if _is_explicit_image_request(question) else []

    if not relevant_nodes:
        if role == "staff":
            return {
                "text": (
                    "I wasn't able to find information matching your question in the company documents "
                    "(policies, workflows, or services). Try rephrasing, or check if your question relates to:\n\n"
                    "- Company policies (hours, staffing, financial targets, compliance)\n"
                    "- Standard operating procedures and workflows\n"
                    "- Clinical services and pricing\n\n"
                    "If you need help beyond these topics, please contact the Practice Manager."
                ),
                "images": images,
            }
        return {
            "text": (
                "I wasn't able to find information matching your question in our documents. "
                "Here are some topics I can help with:\n\n"
                "- Services we offer (cleanings, fillings, crowns, Invisalign, etc.)\n"
                "- Office hours and scheduling\n"
                "- What to expect during your visit\n"
                "- Insurance and payment information\n\n"
                "Try rephrasing your question, or call our front desk for personalized assistance."
            ),
            "images": images,
        }

    context = "\n\n---\n\n".join(node.get_content() for node in relevant_nodes)
    feedback_examples = get_positive_feedback_context(question)
    feedback_context = ""
    if feedback_examples:
        formatted = []
        for idx, item in enumerate(feedback_examples, start=1):
            formatted.append(
                f"{idx}. Similar question: {item['question']}\n"
                f"   Helpful answer style: {item['answer']}"
            )
        feedback_context = (
            "Use these positively rated examples as style guidance when relevant. "
            "Do not copy verbatim, and do not contradict the provided document context.\n\n"
            + "\n\n".join(formatted)
            + "\n\n"
        )

    system_prompt = get_system_prompt(role)
    user_message = (
        f"Use only the following context from DentalBoutique documents to answer the question. "
        f"If the context doesn't contain enough information, say so.\n\n"
        f"{feedback_context}"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )

    llm = Settings.llm
    response = llm.complete(
        f"{system_prompt}\n\n{user_message}",
    )
    return {"text": response.text.strip(), "images": images}
