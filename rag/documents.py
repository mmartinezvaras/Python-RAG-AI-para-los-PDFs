"""The document collection: public PDFs downloaded from their official source.

The default dataset is Spain's Workers' Statute (Estatuto de los Trabajadores), the
consolidated text published by the BOE. Long, real, in Spanish and full of precise numbers
(days, hours, months): a good test for a RAG system, and every answer can be checked
against the official PDF page it cites.

Run ``python -m rag.documents`` to download anything missing.
"""

from __future__ import annotations

import time
import urllib.error
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


class DownloadError(RuntimeError):
    pass


def _fetch(url: str, attempts: int = 4, timeout: int = 60) -> bytes:
    """GET with retries: the BOE server sometimes doesn't answer cloud machines on the first try."""
    delay = 3.0
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (rag-over-pdfs demo)"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == attempts:
                raise DownloadError(
                    f"Could not download {url} after {attempts} attempts ({exc}). The server may be busy: "
                    "try again in a few minutes, or download the PDF in a browser and put it in data/."
                ) from exc
            print(f"   attempt {attempt} failed ({exc}); retrying in {delay:.0f} s")
            time.sleep(delay)
            delay *= 2
    raise DownloadError(url)  # pragma: no cover


def download_missing(data_path: Path = config.DATA_PATH) -> list[str]:
    """Download the dataset PDFs that are not in ``data_path`` yet. Returns what was downloaded.

    The Workers' Statute PDF is committed to the repository, so normally nothing is downloaded."""
    data_path.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for doc in DOCUMENTS:
        target = data_path / doc.filename
        if target.exists() and target.stat().st_size > 0:
            continue
        print(f"⬇️  Downloading {doc.title}")
        content = _fetch(doc.url)
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
