"""OpenRouter-compatible embedding using OpenAI API format (no extra LlamaIndex package)."""
import time
from typing import Any, List

import httpx
from llama_index.core.base.embeddings.base import BaseEmbedding

_MAX_RETRIES = 8
_MAX_CHARS = 30_000


def _call_openrouter(
    url: str, api_key: str, model: str, input_data: str | list[str],
) -> dict:
    """POST to OpenRouter /embeddings with retry + backoff. Returns parsed JSON."""
    payload: dict[str, Any] = {"model": model, "input": input_data}
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        if attempt > 0:
            time.sleep(min(2 ** attempt, 30))
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            if resp.status_code == 429:
                last_error = ValueError("Rate limited (429)")
                continue
            resp.raise_for_status()
            data = resp.json()
            if "data" in data and data["data"]:
                return data
            # 200 but empty — transient provider failure
            err = data.get("error")
            if isinstance(err, dict):
                msg = err.get("message", str(err))
            elif isinstance(err, str):
                msg = err
            else:
                msg = str(data)
            last_error = ValueError(f"No embedding data: {msg} (model={model!r})")
            continue
        except httpx.HTTPStatusError as e:
            last_error = ValueError(f"HTTP {e.response.status_code}: {e.response.text[:300]}")
            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                break
        except httpx.TransportError as e:
            last_error = e
    raise last_error


class OpenRouterEmbedding(BaseEmbedding):
    """Embedding model for OpenRouter (OpenAI-compatible API with provider/model names)."""

    def __init__(
        self,
        model_name: str,
        api_base: str,
        api_key: str,
        embed_batch_size: int = 10,
        **kwargs,
    ):
        super().__init__(model_name=model_name, embed_batch_size=embed_batch_size, **kwargs)
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key

    def _get_text_embedding(self, text: str) -> List[float]:
        if len(text) > _MAX_CHARS:
            text = text[:_MAX_CHARS]
        data = _call_openrouter(
            f"{self._api_base}/embeddings", self._api_key, self.model_name, text,
        )
        return list(data["data"][0]["embedding"])

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch embed — send all texts in one API call (OpenRouter supports this)."""
        trimmed = [t[:_MAX_CHARS] for t in texts]
        data = _call_openrouter(
            f"{self._api_base}/embeddings", self._api_key, self.model_name, trimmed,
        )
        # OpenRouter returns data sorted by index
        sorted_items = sorted(data["data"], key=lambda x: x["index"])
        return [list(item["embedding"]) for item in sorted_items]

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_text_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    @classmethod
    def class_name(cls) -> str:
        return "OpenRouterEmbedding"
