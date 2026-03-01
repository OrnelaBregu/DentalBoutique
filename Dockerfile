FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps commonly needed by Pillow/ML wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only PyTorch first to avoid pulling the large GPU wheel (~2.5 GB).
# sentence-transformers will reuse this installation instead of upgrading to GPU torch.
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r requirements.txt

COPY . .

# Persist vectors/models/feedback outside container layer
ENV VECTOR_STORE_PATH=/data/chroma \
    MODEL_CACHE_DIR=/data/model_cache \
    FEEDBACK_FILE_PATH=/data/feedback.jsonl \
    EXTRACTED_IMAGES_DIR=/app/static/indexed_images

EXPOSE 8080

CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "180", "--bind", "0.0.0.0:8080", "app:app"]
