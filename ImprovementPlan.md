# DentalBoutique RAG Assistant — Improvement Plan

---

## Project Description

A Flask-based, role-aware multimodal RAG assistant for a dental clinic knowledge base. Answers questions for two personas (patient, staff) using only ingested internal documents. Optionally returns relevant document images when explicitly requested.

---

## End-to-End Architecture

### Ingestion (`rag/ingestion.py`)
- Reads `company_*.md` and `company_*.docx` from project root
- Extracts DOCX text (XML parsing) and images (word/media/)
- Chunks text via `MarkdownNodeParser`
- Builds two Chroma collections:
  - `dental_boutique_text` — text chunk embeddings
  - `dental_boutique_images` — image embeddings + CLIP-predicted topic metadata
- Rebuilds collections fresh on every run (destructive reindex)

### Retrieval + Generation (`rag/retriever.py`)
- Retrieves top-k text chunks by vector similarity, filtered by MIN_SCORE threshold
- Rewrites follow-up questions into standalone queries using chat history
- Injects positive feedback examples as answer-style guidance
- Applies role-specific system prompt (`rag/prompts.py`)
- Generates final answer via LLM
- Image retrieval guardrails:
  - Only triggered when user explicitly uses keywords (show, image, photo, etc.)
  - Topic-matching filter prevents cross-procedure image leakage
  - Similarity threshold gates image inclusion

### Feedback Loop (`rag/feedback.py`, `/feedback`)
- UI captures thumbs up / thumbs down per answer
- All feedback stored in JSONL (full audit trail)
- Only positive feedback indexed in `dental_boutique_feedback_positive`
- On similar future questions, pulls top-k positive examples as prompt context

### Frontend (`templates/index.html`)
- Role selector (patient / staff), chat thread, image rendering
- Thumbs up / down controls with submission state management

---

## Models & Tech Stack

| Layer | Component | Detail |
|---|---|---|
| Text embeddings | `BAAI/bge-small-en-v1.5` | Chunk, query, and feedback embeddings (local CPU) |
| Image embeddings | `clip-ViT-B-32` | Image vectorization, text-to-image matching, topic labeling (local CPU) |
| LLM | Configurable via `LLM_MODEL` | Default: `openai/gpt-4o` via OpenRouter or OpenAI |
| Vector DB | ChromaDB | Persistent local store (`data/chroma`) |
| Orchestration | LlamaIndex | Text index / retrieval / generation pipeline |
| Web | Flask + Gunicorn | Served on port 8080 |
| Deployment | Fly.io | `yyz` region, 2 shared CPUs, 4 GB RAM, 5 GB persistent volume |

---

## Known Deployment Issues (Resolved)

- Docker image exceeded 8 GB limit — fixed by installing CPU-only PyTorch before `requirements.txt`
<<<<<<< HEAD
- Image ingestion OOM during `fly ssh console` ingestion — worked around by running ingestion locally and uploading ChromaDB via `fly sftp`
=======
- Port mismatch between Dockerfile (hardcoded 8000) and fly.io default (8080) — fixed
- `*.md` / `*.docx` files excluded from Docker image by `.dockerignore` — fixed; company docs now included
- Image ingestion OOM during `fly ssh console` ingestion — worked around by running ingestion locally and uploading ChromaDB via `fly sftp`
- `chroma.tar.gz` accidentally committed to git — removed and added to `.gitignore`
>>>>>>> 536ee6e (readiness to deploy on streamlit)
- `auto_stop_machines = "stop"` causing cold-start delays — changed to `"off"`

---

## Improvement Roadmap (Priority Order)

### P0 — Startup Performance (immediate)
**Problem:** First chat request pays a ~10s model-load penalty because the embedding index loads lazily.
**Fix:** Pre-warm `_get_index()` at gunicorn startup so the model is in memory before the first request arrives.
**Files:** `app.py`, `rag/retriever.py`

---

### P1 — Image Precision
**Problem:** CLIP-predicted topic labels can have edge mismatches (e.g., a crown image labeled as a bridge).
**Fix:**
- Add manual/canonical tags per image during ingestion, derived from document section headings or a sidecar JSON metadata file
- Filter by manual tags first, fall back to CLIP similarity only when manual tag is absent
- **Files:** `rag/ingestion.py`, `rag/retriever.py`

---

### P2 — Retrieval Ranking
**Problem:** Fixed similarity thresholds (`MIN_SCORE=0.3`, hardcoded in `retriever.py` instead of `config.py`) treat all queries equally regardless of intent.
**Fix:**
- Move `MIN_SCORE` to `config.py`
- Add a cross-encoder reranker step after initial retrieval to re-score and re-order chunks
- Consider hybrid retrieval: BM25 sparse + dense vector, merged via Reciprocal Rank Fusion
- **Files:** `rag/retriever.py`, `config.py`

---

### P3 — Chunking Quality
**Problem:** `MarkdownNodeParser` creates chunks based on markdown structure only; no overlap, no section-title propagation.
**Fix:**
- Switch to semantic chunking with configurable overlap (e.g., 128 token overlap)
- Preserve section title and source document reference in each chunk's metadata
- Use metadata for citations in generated answers ("According to company_policies.md, section 3…")
- **Files:** `rag/ingestion.py`

---

### P4 — Feedback Loop Safety
**Problem:** All positive feedback is equally weighted, role-agnostic, and unmoderated. Negative feedback is logged but never used.
**Fix:**
- Add decay/recency weighting (older feedback scores lower)
- Scope feedback collections by role (`feedback_positive_patient`, `feedback_positive_staff`)
- Use negative feedback to inject "avoid this pattern" guidance into the LLM prompt
- Add basic content validation before indexing (minimum length, no profanity)
- **Files:** `rag/feedback.py`, `rag/retriever.py`

---

### P5 — Evaluation Harness
**Problem:** No automated testing. Changes to prompts/models/thresholds are validated only by manual testing.
**Fix:**
- Build a test set of ~20 representative questions (text-only + image-request, patient + staff)
- Track: answer faithfulness, retrieval precision@k, image mismatch rate, feedback acceptance rate
- Run regression suite before any threshold or model change
- **Files:** `tests/` (new directory)

---

### P6 — Performance & Cost
**Problem:** Every query embeds the question on CPU (slow), calls GPT-4o regardless of question complexity (expensive).
**Fix:**
- Cache embeddings and retrieval results for repeated questions (e.g., Redis or in-memory LRU)
- Tiered LLM strategy: route simple FAQ intents to a smaller/faster model (e.g., `gpt-4o-mini`), fall back to `gpt-4o` for complex or ambiguous queries
- **Files:** `rag/retriever.py`, `config.py`

---

### P7 — Technical Debt
- `rag/openrouter_embedding.py` is dead code — never imported. Either integrate as the embedding API fallback or delete.
- Chat history `slice(-8)` in `index.html` is inconsistent with `HISTORY_MAX_TURNS=4` in `config.py` — align them.
- **Files:** `rag/openrouter_embedding.py`, `templates/index.html`
