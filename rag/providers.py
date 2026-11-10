"""Model providers behind two tiny interfaces, so the pipeline doesn't care where models run.

* Embeddings: ``embed_documents(texts) -> list[vector]`` and ``embed_query(text) -> vector``
* LLM:        ``complete(prompt) -> str`` and ``stream(prompt) -> Iterator[str]``

Providers: Ollama (local, default), any OpenAI-compatible HTTP API (Gemini, Groq, OpenAI,
LM Studio...) and AWS Bedrock for embeddings. The OpenAI-compatible client uses only the
standard library, so the online demo needs no extra SDK.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator

from rag import config

# ------------------------------------------------------------------------------------------
# OpenAI-compatible HTTP client
# ------------------------------------------------------------------------------------------


class ApiError(RuntimeError):
    pass


def _post(base_url: str, path: str, api_key: str, payload: dict, stream: bool = False, retries: int = 5):
    """POST JSON with retries on rate limits / transient errors (free tiers return 429 often)."""
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    delay = 2.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                # A per-minute limit only clears after a full minute.
                wait = float(exc.headers.get("Retry-After") or (61 if exc.code == 429 else delay))
                time.sleep(min(wait, 60))
                delay *= 2
                continue
            detail = exc.read().decode(errors="replace")[:500]
            raise ApiError(f"{exc.code} from {url}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            # The free tier sometimes stalls a response until the read times out: retry those too.
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise ApiError(f"Can't reach {url}: {getattr(exc, 'reason', exc)}") from exc
    raise ApiError("unreachable")  # pragma: no cover


def parse_sse_deltas(lines: Iterable[bytes | str]) -> Iterator[str]:
    """Yield the text deltas of an OpenAI-style streaming (server-sent events) response."""
    for raw in lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        try:
            choices = json.loads(data).get("choices") or []
        except json.JSONDecodeError:
            continue
        for choice in choices:
            text = (choice.get("delta") or {}).get("content")
            if text:
                yield text


class OpenAICompatibleLLM:
    def __init__(self, model: str, base_url: str, api_key: str, temperature: float = 0.0):
        self.model, self.base_url, self.api_key, self.temperature = model, base_url, api_key, temperature

    def _payload(self, prompt: str, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": stream,
        }

    def complete(self, prompt: str) -> str:
        with _post(self.base_url, "chat/completions", self.api_key, self._payload(prompt, False)) as resp:
            data = json.load(resp)
        return (data["choices"][0]["message"].get("content") or "").strip()

    def stream(self, prompt: str) -> Iterator[str]:
        with _post(self.base_url, "chat/completions", self.api_key, self._payload(prompt, True), stream=True) as resp:
            yield from parse_sse_deltas(resp)


class OpenAICompatibleEmbeddings:
    def __init__(self, model: str, base_url: str, api_key: str, batch_size: int = 64):
        self.model, self.base_url, self.api_key, self.batch_size = model, base_url, api_key, batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        # Free tiers count every text as one request (Gemini: 100 a minute), so pace the batches.
        per_minute = int(os.getenv("RAG_EMBED_PER_MINUTE") or 0)
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            if per_minute and i:
                time.sleep(60 * len(batch) / per_minute)
            with _post(self.base_url, "embeddings", self.api_key, {"model": self.model, "input": batch}) as resp:
                data = json.load(resp)["data"]
            # OpenAI numbers each item with "index"; Gemini's compatible API omits it and
            # returns them in input order.
            if all("index" in item for item in data):
                data = sorted(data, key=lambda d: d["index"])
            if len(data) != len(batch):
                raise ApiError(f"Asked for {len(batch)} embeddings, got {len(data)}")
            vectors.extend(item["embedding"] for item in data)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


# ------------------------------------------------------------------------------------------
# Ollama
# ------------------------------------------------------------------------------------------


class OllamaChat:
    def __init__(self, model: str, temperature: float = 0.0):
        from langchain_ollama import OllamaLLM

        self._llm = OllamaLLM(model=model, temperature=temperature, base_url=config.OLLAMA_URL)

    def complete(self, prompt: str) -> str:
        return self._llm.invoke(prompt).strip()

    def stream(self, prompt: str) -> Iterator[str]:
        yield from self._llm.stream(prompt)


class TaskPrefixEmbeddings:
    """nomic-embed-text was trained with task prefixes; using them improves retrieval."""

    def __init__(self, inner, doc_prefix: str = "search_document: ", query_prefix: str = "search_query: "):
        self.inner, self.doc_prefix, self.query_prefix = inner, doc_prefix, query_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(self.query_prefix + text)


# ------------------------------------------------------------------------------------------
# Factories
# ------------------------------------------------------------------------------------------


def _require_key():
    if not config.OPENAI_API_KEY:
        raise ApiError("OPENAI_API_KEY is not set (needed for the OpenAI-compatible provider).")


def get_embedding_function():
    provider = config.EMBEDDING_PROVIDER
    if provider == "openai":
        _require_key()
        return OpenAICompatibleEmbeddings(config.EMBED_MODEL, config.OPENAI_BASE_URL, config.OPENAI_API_KEY)
    if provider == "bedrock":
        import os

        from langchain_aws import BedrockEmbeddings

        return BedrockEmbeddings(
            credentials_profile_name=os.getenv("AWS_PROFILE", "default"),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
    from langchain_ollama import OllamaEmbeddings

    emb = OllamaEmbeddings(model=config.EMBED_MODEL, base_url=config.OLLAMA_URL)
    return TaskPrefixEmbeddings(emb) if "nomic" in config.EMBED_MODEL else emb


def get_llm(model: str | None = None):
    model = model or config.LLM_MODEL
    if config.LLM_PROVIDER == "openai":
        _require_key()
        return OpenAICompatibleLLM(model, config.OPENAI_BASE_URL, config.OPENAI_API_KEY)
    return OllamaChat(model)
