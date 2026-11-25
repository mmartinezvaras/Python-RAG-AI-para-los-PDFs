"""The OpenAI-compatible client (used for the online demo) against a local fake server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from rag import providers
from rag.providers import OpenAICompatibleEmbeddings, OpenAICompatibleLLM, parse_sse_deltas


def test_parse_sse_deltas():
    lines = [
        b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
        b"\n",
        b'data: {"choices":[{"delta":{"content":"Trein"}}]}\n',
        b": keep-alive comment\n",
        b'data: {"choices":[{"delta":{"content":"ta [1]"}}]}\n',
        b"data: [DONE]\n",
        b'data: {"choices":[{"delta":{"content":"ignored"}}]}\n',
    ]
    assert "".join(parse_sse_deltas(lines)) == "Treinta [1]"


class FakeOpenAI(BaseHTTPRequestHandler):
    calls: list = []
    fail_first = 0
    with_index = True  # False behaves like Gemini's OpenAI-compatible API

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOpenAI.calls.append((self.path, self.headers.get("Authorization"), body))
        if FakeOpenAI.fail_first > 0:
            FakeOpenAI.fail_first -= 1
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.end_headers()
            return
        if self.path.endswith("/embeddings"):
            if FakeOpenAI.with_index:
                data = [{"index": i, "embedding": [float(len(t)), 1.0]} for i, t in enumerate(body["input"])]
                data = list(reversed(data))  # out of order on purpose
            else:
                data = [{"embedding": [float(len(t)), 1.0]} for t in body["input"]]
            payload = json.dumps({"data": data}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)
        elif body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for piece in ["Hola", " mundo"]:
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': piece}}]})}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            payload = json.dumps({"choices": [{"message": {"content": " Hola mundo "}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    FakeOpenAI.calls, FakeOpenAI.fail_first, FakeOpenAI.with_index = [], 0, True
    httpd = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1/"
    httpd.shutdown()


def test_chat_complete_and_stream(server):
    llm = OpenAICompatibleLLM("some-model", server, "secret")
    assert llm.complete("hola") == "Hola mundo"
    assert "".join(llm.stream("hola")) == "Hola mundo"
    path, auth, body = FakeOpenAI.calls[0]
    assert path == "/v1/chat/completions" and auth == "Bearer secret"
    assert body["model"] == "some-model" and body["temperature"] == 0


def test_embeddings_are_batched_and_ordered(server):
    emb = OpenAICompatibleEmbeddings("emb-model", server, "secret", batch_size=2)
    vectors = emb.embed_documents(["a", "bb", "ccc"])
    assert vectors == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]
    assert len(FakeOpenAI.calls) == 2  # 2 + 1 texts
    assert emb.embed_query("dddd") == [4.0, 1.0]


def test_embeddings_without_index_field_like_gemini(server):
    FakeOpenAI.with_index = False
    emb = OpenAICompatibleEmbeddings("gemini-embedding-001", server, "secret", batch_size=2)
    assert emb.embed_documents(["a", "bb", "ccc"]) == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]


def test_retries_on_rate_limit(server):
    FakeOpenAI.fail_first = 2
    assert OpenAICompatibleLLM("m", server, "k").complete("x") == "Hola mundo"
    assert len(FakeOpenAI.calls) == 3


# ---------- Several models, so the demo keeps answering when one runs out of quota ----------


class _Model:
    def __init__(self, name, fails=False):
        self.model, self.fails, self.calls = name, fails, 0

    def complete(self, prompt):
        self.calls += 1
        if self.fails:
            raise providers.ApiError("429 quota", status=429)
        return f"answer from {self.model}"

    def stream(self, prompt):
        self.calls += 1
        if self.fails:
            raise providers.ApiError("429 quota", status=429)
        yield f"answer from {self.model}"


def test_fallback_uses_the_next_model_when_one_is_out_of_quota():
    main, backup = _Model("main", fails=True), _Model("backup")
    llm = providers.FallbackLLM([main, backup])
    assert "".join(llm.stream("hola")) == "answer from backup"
    assert llm.complete("hola") == "answer from backup"
    assert llm.used == "backup"


def test_a_model_out_of_quota_rests_and_is_tried_again_later():
    now = [0.0]
    main, backup = _Model("main", fails=True), _Model("backup")
    llm = providers.FallbackLLM([main, backup], clock=lambda: now[0])
    llm.complete("a")
    llm.complete("b")
    assert main.calls == 1  # not asked again while resting
    now[0] += providers.FallbackLLM.REST_SECONDS + 1
    main.fails = False
    assert llm.complete("c") == "answer from main"


def test_fallback_raises_when_every_model_fails():
    llm = providers.FallbackLLM([_Model("a", fails=True), _Model("b", fails=True)])
    with pytest.raises(providers.ApiError) as info:
        "".join(llm.stream("hola"))
    assert info.value.status == 429 and "a:" in str(info.value) and "b:" in str(info.value)


def test_the_demo_does_not_make_a_visitor_wait_a_minute_for_a_rate_limit(server, monkeypatch):
    waits = []
    monkeypatch.setattr(providers.time, "sleep", waits.append)
    FakeOpenAI.fail_first = 5
    llm = OpenAICompatibleLLM("m", server, "secret", retries=1, max_wait=3)
    with pytest.raises(providers.ApiError):
        llm.complete("hola")
    assert waits and max(waits) <= 3
