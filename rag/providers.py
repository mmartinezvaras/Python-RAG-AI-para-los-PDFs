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
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _post(
    base_url: str,
    path: str,
    api_key: str,
    payload: dict,
    stream: bool = False,
    retries: int = 5,
    max_wait: float = 60,
):
    """POST JSON with retries on rate limits / transient errors (free tiers return 429 often).

    ``max_wait``: the longest pause between attempts. Batch jobs (indexing, evaluation) can wait a
    full minute for a per-minute limit to clear; a visitor of the demo can't, so the demo uses a
    short wait and moves on to another model instead (see ``FallbackLLM``)."""
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
                time.sleep(min(wait, max_wait))
                delay *= 2
                continue
            detail = exc.read().decode(errors="replace")[:500]
            raise ApiError(f"{exc.code} from {url}: {detail}", status=exc.code) from exc
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
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.0,
        retries: int = 5,
        max_wait: float = 60,
    ):
        self.model, self.base_url, self.api_key, self.temperature = model, base_url, api_key, temperature
        self.retries, self.max_wait = retries, max_wait

    def _payload(self, prompt: str, stream: bool) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "stream": stream,
        }

    def complete(self, prompt: str) -> str:
        payload = self._payload(prompt, False)
        with _post(self.base_url, "chat/completions", self.api_key, payload, False, self.retries, self.max_wait) as resp:
            data = json.load(resp)
        return (data["choices"][0]["message"].get("content") or "").strip()

    def stream(self, prompt: str) -> Iterator[str]:
        payload = self._payload(prompt, True)
        with _post(self.base_url, "chat/completions", self.api_key, payload, True, self.retries, self.max_wait) as resp:
            yield from parse_sse_deltas(resp)


class FallbackLLM:
    """Several models tried in order: when one fails (daily quota used up, model withdrawn,
    server error), the next one answers. On Gemini's free tier every model has its own quota,
    so a list of models multiplies the questions the demo can answer in a day."""

    REST_SECONDS = 15 * 60  # a model that ran out of quota is skipped for a while

    def __init__(self, llms: list, clock=time.monotonic):
        if not llms:
            raise ValueError("FallbackLLM needs at least one model")
        self.llms = llms
        self.model = llms[0].model
        self.used: str | None = None  # the model that produced the last answer
        self._clock = clock
        self._resting: dict[str, float] = {}  # model -> when it can be tried again
        self._last_status: int | None = None

    def _order(self) -> list:
        """Models that aren't resting first, in the configured order; resting ones last, so they
        are still tried if every other model fails."""
        now = self._clock()
        ready = [m for m in self.llms if self._resting.get(m.model, 0) <= now]
        return ready + [m for m in self.llms if m not in ready]

    def _failed(self, llm, exc: ApiError, errors: list[str]) -> None:
        errors.append(f"{llm.model}: {exc}")
        self._last_status = exc.status
        # Out of quota (429), withdrawn or not free (4xx) or down (5xx): give it a rest either way.
        self._resting[llm.model] = self._clock() + self.REST_SECONDS

    def complete(self, prompt: str) -> str:
        errors: list[str] = []
        for llm in self._order():
            try:
                text = llm.complete(prompt)
            except ApiError as exc:
                self._failed(llm, exc, errors)
                continue
            self.used = llm.model
            return text
        raise ApiError(" | ".join(errors), status=self._last_status)

    def stream(self, prompt: str) -> Iterator[str]:
        errors: list[str] = []
        for llm in self._order():
            pieces = llm.stream(prompt)
            try:
                # The request is sent when the first piece is asked for: a quota error shows up
                # here, before anything reached the visitor, so the next model can take over.
                first = next(pieces, None)
            except ApiError as exc:
                self._failed(llm, exc, errors)
                continue
            self.used = llm.model
            if first is not None:
                yield first
            yield from pieces
            return
        raise ApiError(" | ".join(errors), status=self._last_status)


class OpenAICompatibleEmbeddings:
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        batch_size: int = 64,
        query_retries: int = 5,
        query_max_wait: float = 60,
    ):
        self.model, self.base_url, self.api_key, self.batch_size = model, base_url, api_key, batch_size
        # A visitor's question can't wait minutes; indexing (embed_documents) can.
        self.query_retries, self.query_max_wait = query_retries, query_max_wait

    def embed_documents(self, texts: list[str], retries: int = 5, max_wait: float = 60) -> list[list[float]]:
        vectors: list[list[float]] = []
        # Free tiers count every text as one request (Gemini: 100 a minute), so pace the batches.
        per_minute = int(os.getenv("RAG_EMBED_PER_MINUTE") or 0)
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            if per_minute and i:
                time.sleep(60 * len(batch) / per_minute)
            payload = {"model": self.model, "input": batch}
            with _post(self.base_url, "embeddings", self.api_key, payload, False, retries, max_wait) as resp:
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
        return self.embed_documents([text], self.query_retries, self.query_max_wait)[0]


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
        quick = {"query_retries": 1, "query_max_wait": 3} if config.PUBLIC_DEMO else {}
        return OpenAICompatibleEmbeddings(config.EMBED_MODEL, config.OPENAI_BASE_URL, config.OPENAI_API_KEY, **quick)
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
    """The model that writes the answers. With no ``model`` given and an OpenAI-compatible
    provider, the configured fallbacks (``RAG_LLM_FALLBACKS``) stand behind the main model.

    In the public demo a visitor is waiting, so each model gets one quick retry before the next
    one is tried; batch jobs (evaluation) keep the patient retries."""
    if config.LLM_PROVIDER != "openai":
        return OllamaChat(model or config.LLM_MODEL)
    _require_key()
    patience = {"retries": 1, "max_wait": 3} if config.PUBLIC_DEMO else {}

    def one(name: str) -> OpenAICompatibleLLM:
        return OpenAICompatibleLLM(name, config.OPENAI_BASE_URL, config.OPENAI_API_KEY, **patience)

    if model:
        return one(model)
    names = [config.LLM_MODEL] + [m for m in config.LLM_FALLBACKS if m != config.LLM_MODEL]
    return FallbackLLM([one(m) for m in dict.fromkeys(names)])
