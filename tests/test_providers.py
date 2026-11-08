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
            data = [{"index": i, "embedding": [float(len(t)), 1.0]} for i, t in enumerate(body["input"])]
            payload = json.dumps({"data": list(reversed(data))}).encode()  # out of order on purpose
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
    FakeOpenAI.calls, FakeOpenAI.fail_first = [], 0
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


def test_retries_on_rate_limit(server):
    FakeOpenAI.fail_first = 2
    assert OpenAICompatibleLLM("m", server, "k").complete("x") == "Hola mundo"
    assert len(FakeOpenAI.calls) == 3
