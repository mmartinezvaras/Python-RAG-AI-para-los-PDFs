"""Downloading the dataset: retries and a clear error when the server doesn't answer."""

import urllib.error

import pytest

from rag import documents


def test_fetch_retries_then_explains(monkeypatch):
    calls = []

    def fail(req, timeout):
        calls.append(req.full_url)
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(documents.urllib.request, "urlopen", fail)
    monkeypatch.setattr(documents.time, "sleep", lambda s: None)
    with pytest.raises(documents.DownloadError, match="put it in data/"):
        documents._fetch("https://example.org/x.pdf", attempts=3)
    assert len(calls) == 3


def test_existing_pdf_is_not_downloaded_again(tmp_path, monkeypatch):
    (tmp_path / "estatuto_trabajadores.pdf").write_bytes(b"%PDF-1.4 ...")
    monkeypatch.setattr(documents, "_fetch", lambda url: pytest.fail("should not download"))
    assert documents.download_missing(tmp_path) == []
