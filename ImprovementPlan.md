Precise Project Description
This project is a Flask-based, role-aware multimodal RAG assistant for a dental clinic knowledge base.
It answers questions for two personas (patient, staff) using only ingested internal documents, and can optionally return relevant document images only when explicitly requested.
End-to-end flow
Ingestion (rag/ingestion.py)
Reads company_*.md and company_*.docx
Extracts DOCX text + images
Chunks text via MarkdownNodeParser
Builds two Chroma collections:
dental_boutique_text (text chunks)
dental_boutique_images (image embeddings + metadata)
Rebuilds collections each run (fresh index)
Retrieval + Generation (rag/retriever.py)
Retrieves top-k text chunks by vector similarity
Filters weak text matches (MIN_SCORE)
Applies role-specific prompt (rag/prompts.py)
Generates final answer with LLM
Image retrieval guardrails:
only if user explicitly asks for images/photos
topic matching filter (e.g., implant query should not return root-canal-topic images)
similarity threshold for image acceptance
Feedback loop (rag/feedback.py, /feedback)
UI captures 👍/👎 per answer
Stores all feedback in JSONL
Indexes only positive feedback in dental_boutique_feedback_positive
On future similar questions, pulls positive examples and uses them as answer-style guidance
Frontend (templates/index.html)
Role selector, chat thread, optional image rendering
Feedback controls with thumbs up/down
Models/Tech Used by RAG Stage
Text embedding model
BAAI/bge-small-en-v1.5
Used for:
text document chunk embeddings
text query embeddings
feedback-similarity embeddings (positive examples)
Image embedding model
sentence-transformers/clip-ViT-B-32
Used for:
image vectorization
text-to-image query matching
automatic image topic labeling during ingestion
LLM for answer generation
Configurable LLM_MODEL (default: openai/gpt-4o)
Accessed via OpenRouter when OPENROUTER_API_KEY exists, otherwise OpenAI
Vector DB
ChromaDB persistent local store (data/chroma)
Orchestration
LlamaIndex for text index/retrieval/generation pipeline
Supporting stack
Flask, python-dotenv, Pillow, sentence-transformers
What should be optimized next (priority order)
1) Improve image precision with deterministic labels
Current topic labels are CLIP-predicted, so edge mismatches can still happen.
Best upgrade: add manual/canonical tags per image during ingestion (or from document section metadata), and filter by those tags first.
2) Strengthen retrieval ranking
Replace fixed thresholds with calibrated thresholds per intent.
Add reranking step for text chunks (cross-encoder reranker) before generation.
Consider hybrid retrieval (BM25 + dense vectors).
3) Improve chunking quality
Use semantic chunking and chunk overlap instead of only markdown-structure chunking.
Preserve section titles and source references in metadata for better answer grounding/citations.
4) Make feedback loop safer and smarter
Currently positive feedback influences style; add:
decay/recency weighting
role-scoped feedback weighting
explicit negative-feedback penalties (avoid repeated bad answer patterns)
moderation/validation of feedback data before indexing
5) Add evaluation harness
Create a test set of representative questions (text-only + image-request)
Track metrics: answer faithfulness, retrieval precision@k, image mismatch rate, feedback acceptance rate
Run regressions before updates to prompts/models/thresholds
6) Performance and cost optimization
Cache embeddings and retrieval outputs for repeated questions
Preload models once (warm startup)
Consider smaller/faster LLM for simple FAQ intents + fallback to stronger model
7) Clean technical debt
rag/openrouter_embedding.py appears present but not in active path; either integrate or remove to avoid confusion.