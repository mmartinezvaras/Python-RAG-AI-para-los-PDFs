"""The document collection: public PDFs downloaded from their official source.

The default dataset is Spain's Workers' Statute (Estatuto de los Trabajadores), the
consolidated text published by the BOE. Long, real, in Spanish and full of precise numbers
(days, hours, months): a good test for a RAG system, and every answer can be checked
against the official PDF page it cites.

Run ``python -m rag.documents`` to download anything missing.
"""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from pathlib import Path

from rag import config


@dataclass(frozen=True)
class SourceDoc:
    filename: str
    title: str
    url: str


DOCUMENTS = [
    SourceDoc(
        filename="estatuto_trabajadores.pdf",
        title="Estatuto de los Trabajadores (texto consolidado, BOE)",
        url="https://www.boe.es/buscar/pdf/2015/BOE-A-2015-11430-consolidado.pdf",
    ),
]

_BY_FILENAME = {d.filename: d for d in DOCUMENTS}


def source_info(filename: str) -> SourceDoc | None:
    return _BY_FILENAME.get(Path(filename).name)


def page_link(filename: str, page_index: int | None) -> str | None:
    """Link to the official PDF, opened at the cited page (``#page=`` is 1-based)."""
    doc = source_info(filename)
    if doc is None:
        return None
    return f"{doc.url}#page={page_index + 1}" if page_index is not None else doc.url


def download_missing(data_path: Path = config.DATA_PATH) -> list[str]:
    """Download the dataset PDFs that are not in ``data_path`` yet. Returns what was downloaded."""
    data_path.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for doc in DOCUMENTS:
        target = data_path / doc.filename
        if target.exists() and target.stat().st_size > 0:
            continue
        print(f"⬇️  Downloading {doc.title}")
        req = urllib.request.Request(doc.url, headers={"User-Agent": "rag-over-pdfs-demo"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
        if not content.startswith(b"%PDF"):
            raise RuntimeError(f"{doc.url} did not return a PDF")
        tmp = target.with_suffix(".part")
        tmp.write_bytes(content)
        tmp.replace(target)
        downloaded.append(doc.filename)
    return downloaded


if __name__ == "__main__":
    got = download_missing()
    print("✅ Documents ready" + (f" (downloaded: {', '.join(got)})" if got else ""))
