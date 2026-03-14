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

5. **Start the app**
   - **Flask:** `flask run` or `python app.py` → http://127.0.0.1:5000
   - **Streamlit:** `streamlit run streamlit_app.py` → http://127.0.0.1:8501

## Usage

- Choose **Patient** or **Staff** at the top; answers are tailored to that role.
- Type a question and press Send. The bot answers using only the ingested company documents.
- Follow-up questions keep recent chat context (multi-turn memory).
- Images are returned only when explicitly requested (e.g., "show me implant photos").
- Procedure guardrails are applied so image topic must match the requested treatment.
- Use 👍/👎 on assistant answers; positive feedback is reused as guidance for similar future questions.
- Slash commands:
  - `/help` shows available commands
  - `/reindex` rebuilds vectors from `company_*.md` and `company_*.docx`

## Optional env vars (in `.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key (recommended) | — |
| `OPENAI_API_KEY` | OpenAI API key (alternative) | — |
| `VECTOR_STORE_PATH` | Chroma persistence directory | `./data/chroma` |
| `DOCUMENTS_PATH` | Directory containing `company_*.md` | Project root |
| `LLM_MODEL` | Chat model (OpenRouter: e.g. `openai/gpt-4o`) | `openai/gpt-4o` |
| `TEXT_EMBEDDING_MODEL` | Local text embedding model | `qwen/qwen-2.5-72b-instruct` |
| `IMAGE_EMBEDDING_MODEL` | Local image embedding model | `sentence-transformers/clip-ViT-B-32` |
| `MODEL_CACHE_DIR` | Local model cache directory | `./data/model_cache` |
| `TOP_K` | Number of chunks to retrieve per query | `5` |
| `HISTORY_MAX_TURNS` | Number of prior turns used for follow-up rewrite | `4` |
| `IMAGE_TOP_K` | Number of candidate images to return | `3` |
| `IMAGE_MIN_SIMILARITY` | Similarity threshold for image return | `0.22` |
| `FEEDBACK_FILE_PATH` | JSONL log path for feedback events | `./data/feedback.jsonl` |
| `FEEDBACK_TOP_K` | Number of similar positive feedback examples to use | `2` |
| `FEEDBACK_MIN_SIMILARITY` | Similarity threshold for applying positive feedback | `0.35` |

## Deploy with Streamlit Community Cloud (free)

1. Push your repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select your repo, set:
   - **Main file path:** `streamlit_app.py`
   - **Branch:** `main`
4. Add secrets in the app settings (Secrets):
   ```toml
   OPENROUTER_API_KEY = "sk-or-..."
   # or: OPENAI_API_KEY = "sk-..."
   ```
5. Deploy. On first run, click **🔄 Reindex documents** in the sidebar to build the vector index (takes 1–2 minutes).
6. Your app will be live at `https://your-app-name.streamlit.app`.

**Note:** Free tier has ~1GB RAM. If the app crashes, try reducing `TOP_K` or `IMAGE_TOP_K` in secrets.

## Project layout

- `app.py` – Flask app with `/chat` and `/feedback` endpoints  
- `streamlit_app.py` – Streamlit app for local run and Streamlit Cloud deploy  
- `config.py` – Settings from environment  
- `rag/feedback.py` – Persist thumbs feedback and retrieve positive examples  
- `rag/ingestion.py` – Rebuild text + image embeddings and save to Chroma  
- `rag/retriever.py` – Retrieve text context and relevant images per query  
- `rag/prompts.py` – System prompts for Patient vs Staff  
- `templates/index.html` – Chat UI and role selector  
- `static/style.css` – Styles  

Documents: add any `company_*.md` and/or `company_*.docx` files in the project root.
