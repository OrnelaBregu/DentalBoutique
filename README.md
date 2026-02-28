# DentalBoutique RAG Chatbot

A Flask web app that lets **patients** and **staff** ask questions grounded in DentalBoutique company documents (policies, services, workflows). Uses a RAG pipeline (LlamaIndex + Chroma) for text, plus CLIP image embeddings so the assistant can return relevant document images.

## Setup

1. **Clone and enter the project**
   ```bash
   cd /path/to/CodingTest
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment**
   - Copy `.env.example` to `.env`
   - Set **`OPENROUTER_API_KEY`** (recommended) or `OPENAI_API_KEY` for embeddings and LLM

   ```bash
   cp .env.example .env
   # Edit .env and add OPENROUTER_API_KEY=sk-or-... (or OPENAI_API_KEY)
   ```

4. **Run document ingestion (after adding/changing company docs)**  
   Use the project venv so the correct env and code are used:
   ```bash
   .venv/bin/python -m rag.ingestion
   ```
   This rebuilds both collections:
   - text chunks from `company_*.md` and `company_*.docx`
   - extracted images from `company_*.docx` (saved under `static/indexed_images`)
   - vectors in `./data/chroma`

5. **Start the Flask app**
   ```bash
   flask run
   # or: python app.py
   ```
   Open http://127.0.0.1:5000 in a browser.

## Usage

- Choose **Patient** or **Staff** at the top; answers are tailored to that role.
- Type a question and press Send. The bot answers using only the ingested company documents.
- Images are returned only when explicitly requested (e.g., "show me implant photos").
- Procedure guardrails are applied so image topic must match the requested treatment.
- Use 👍/👎 on assistant answers; positive feedback is reused as guidance for similar future questions.

## Optional env vars (in `.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (recommended) | — |
| `OPENAI_API_KEY` | OpenAI API key (alternative) | — |
| `VECTOR_STORE_PATH` | Chroma persistence directory | `./data/chroma` |
| `DOCUMENTS_PATH` | Directory containing `company_*.md` | Project root |
| `LLM_MODEL` | Chat model (OpenRouter: e.g. `openai/gpt-4o`) | `openai/gpt-4o` |
| `TEXT_EMBEDDING_MODEL` | Local text embedding model | `BAAI/bge-small-en-v1.5` |
| `IMAGE_EMBEDDING_MODEL` | Local image embedding model | `sentence-transformers/clip-ViT-B-32` |
| `MODEL_CACHE_DIR` | Local model cache directory | `./data/model_cache` |
| `TOP_K` | Number of chunks to retrieve per query | `5` |
| `IMAGE_TOP_K` | Number of candidate images to return | `3` |
| `IMAGE_MIN_SIMILARITY` | Similarity threshold for image return | `0.22` |
| `FEEDBACK_FILE_PATH` | JSONL log path for feedback events | `./data/feedback.jsonl` |
| `FEEDBACK_TOP_K` | Number of similar positive feedback examples to use | `2` |
| `FEEDBACK_MIN_SIMILARITY` | Similarity threshold for applying positive feedback | `0.35` |

## Project layout

- `app.py` – Flask app with `/chat` and `/feedback` endpoints  
- `config.py` – Settings from environment  
- `rag/feedback.py` – Persist thumbs feedback and retrieve positive examples  
- `rag/ingestion.py` – Rebuild text + image embeddings and save to Chroma  
- `rag/retriever.py` – Retrieve text context and relevant images per query  
- `rag/prompts.py` – System prompts for Patient vs Staff  
- `templates/index.html` – Chat UI and role selector  
- `static/style.css` – Styles  

Documents: add any `company_*.md` and/or `company_*.docx` files in the project root.
