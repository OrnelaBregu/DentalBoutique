# DentalBoutique Command Runbook

Use this file as the default sequence for local development, indexing, and deployment.

## 1) One-time local setup

```bash
cd /Users/ornelabregu/CodingTest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and set at least one key:

- `OPENROUTER_API_KEY=...` (recommended), or
- `OPENAI_API_KEY=...`

## 2) Daily fast-start (recommended order)

**Flask:**
```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -m rag.ingestion
flask run
```
Open: `http://127.0.0.1:5000`

**Streamlit:**
```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -m rag.ingestion
streamlit run streamlit_app.py
```
Open: `http://127.0.0.1:8501`

## 3) Fast dev checks after code changes

```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -m compileall app.py config.py rag
```

## 4) Re-index when docs change

Run this whenever `company_*.md` or `company_*.docx` changes:

```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -m rag.ingestion
```

## 5) Image behavior checks

- Images should appear **only** when user explicitly asks for visuals ("show images/photos...").
- Topic guardrails should prevent mismatched treatment images.

Quick smoke test:

```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -c "from rag.retriever import query; print(query('Tell me about dental implants', role='patient')['images']); print(query('Show me images of dental implants', role='patient')['images'][:3])"
```

Expected:
- First output: `[]`
- Second output: one or more relevant image URLs

## 6) Docker run (local production-like)

```bash
cd /Users/ornelabregu/CodingTest
docker build -t dental-rag .
docker run -p 8000:8000 \
  -e OPENROUTER_API_KEY=YOUR_KEY \
  -e LLM_MODEL=openai/gpt-4o \
  -v $(pwd)/data:/data \
  -v $(pwd)/static/indexed_images:/app/static/indexed_images \
  dental-rag
```

## 7) Streamlit Community Cloud (free deploy)

1. Push repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app.
3. Repo: `OrnelaBregu/DentalBoutique`, main file: `streamlit_app.py`.
4. Add secrets: `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`).
5. Deploy. On first load, click **🔄 Reindex documents** in the sidebar.

## 8) Render deploy notes

- `render.yaml` is ready.
- `postDeployCommand` is not supported in service schema.
- After deploy, run ingestion manually once in Render Shell:

```bash
python -m rag.ingestion
```

## 9) Git quick flow

```bash
cd /Users/ornelabregu/CodingTest
git add .
git commit -m "Update RAG app"
git push origin main
```

## 10) Common recovery commands

If model cache errors occur:

```bash
cd /Users/ornelabregu/CodingTest
mkdir -p data/model_cache data/chroma
```

If index feels stale:

```bash
cd /Users/ornelabregu/CodingTest
source .venv/bin/activate
python -m rag.ingestion
```
