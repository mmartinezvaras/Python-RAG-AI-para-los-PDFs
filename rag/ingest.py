"""Indexing: load PDFs → clean → split → tag articles → stable IDs → sync with ChromaDB.

The index is kept in sync with the ``data/`` folder instead of only growing:

* new chunks are embedded and added,
* chunks whose text changed (the PDF was replaced by a new version) are re-embedded,
* chunks of PDFs that were deleted are removed,
* everything else is left untouched, so nothing is embedded (or paid for) twice.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

from rag import config

# ------------------------------------------------------------------------------------------
# Loading and cleaning
# ------------------------------------------------------------------------------------------

# Running headers/footers that BOE consolidated PDFs repeat on every page. Harmless elsewhere.
_NOISE_LINES = re.compile(
    r"^\s*(BOLET[IÍ]N OFICIAL DEL ESTADO|LEGISLACI[OÓ]N CONSOLIDADA|P[aá]gina\s+\d+(\s+de\s+\d+)?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def clean_text(text: str) -> str:
    text = _NOISE_LINES.sub("", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _relative_source(source: str) -> str:
    path = Path(source).resolve()
    try:
        rel = path.relative_to(config.BASE_DIR)
    except ValueError:
        rel = Path(path.name)
    return rel.as_posix()


def load_documents(data_path: Path | str = config.DATA_PATH) -> list[Document]:
    """One Document per PDF page, with clean text and only the metadata we use."""
    from langchain_community.document_loaders import PyPDFDirectoryLoader

    pages = PyPDFDirectoryLoader(str(data_path), recursive=True).load()
    docs = []
    for page in pages:
        text = clean_text(page.page_content)
        if not text:
            continue
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": _relative_source(page.metadata.get("source", "")),
                    "page": int(page.metadata.get("page") or 0),
                },
            )
        )
    return docs


def split_documents(documents: list[Document]) -> list[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=["\n\n", "\nArtículo ", "\n", ". ", " ", ""],
        keep_separator="start",
    )
    return splitter.split_documents(documents)


# ------------------------------------------------------------------------------------------
# Article tagging (legal texts)
# ------------------------------------------------------------------------------------------

ARTICLE_HEADING = re.compile(r"^\s*Art[ií]culo\s+(\d+(?:\s?(?:bis|ter|quater))?)\s*\.", re.MULTILINE)
_TOC_THRESHOLD = 4  # a chunk with this many article headings is a table of contents


def tag_articles(chunks: list[Document]) -> list[Document]:
    """Record which article(s) of a law each chunk belongs to, so answers can cite "Art. 38".

    A chunk that starts in the middle of an article inherits the article from the previous
    chunk of the same PDF. Chunks that are just a table of contents (many article headings
    in a few lines) are dropped: they match every keyword but answer nothing.
    Documents without "Artículo N." headings simply get an empty ``articles`` field.
    """
    kept: list[Document] = []
    current: dict[str, str | None] = {}
    for chunk in chunks:
        source = chunk.metadata.get("source", "")
        headings = [m.group(1).replace(" ", "") for m in ARTICLE_HEADING.finditer(chunk.page_content)]
        if len(headings) >= _TOC_THRESHOLD:
            continue
        articles = []
        first = ARTICLE_HEADING.search(chunk.page_content)
        starts_with_heading = first is not None and not chunk.page_content[: first.start()].strip()
        if current.get(source) and not starts_with_heading:
            articles.append(current[source])
        articles += [h for h in headings if h not in articles]
        if headings:
            current[source] = headings[-1]
        chunk.metadata["articles"] = ",".join(a for a in articles if a)
        kept.append(chunk)
    return kept


def format_articles(articles: str) -> str:
    """'37,38' → 'Art. 37–38'; '38' → 'Art. 38'; '' → ''."""
    parts = [a for a in articles.split(",") if a]
    if not parts:
        return ""
    return f"Art. {parts[0]}" if len(parts) == 1 else f"Art. {parts[0]}–{parts[-1]}"


# ------------------------------------------------------------------------------------------
# IDs and hashes
# ------------------------------------------------------------------------------------------


def calculate_chunk_ids(chunks: list[Document]) -> list[Document]:
    """IDs like ``data/estatuto_trabajadores.pdf:12:3`` (source : page : chunk on that page)."""
    last_page_id = None
    index = 0
    for chunk in chunks:
        page_id = f"{chunk.metadata.get('source', '')}:{chunk.metadata.get('page')}"
        index = index + 1 if page_id == last_page_id else 0
        chunk.metadata["id"] = f"{page_id}:{index}"
        chunk.metadata["hash"] = content_hash(chunk.page_content)
        last_page_id = page_id
    return chunks


def content_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def plan_sync(desired: dict[str, str], existing: dict[str, str | None]) -> tuple[list[str], list[str]]:
    """Compare the chunks we want ({id: hash}) with the stored ones.

    Returns (ids to embed and add, ids to delete). A changed chunk appears in both.
    """
    to_delete = [i for i, h in existing.items() if desired.get(i) != h]
    to_add = [i for i, h in desired.items() if existing.get(i) != h]
    return to_add, to_delete


def prepare_chunks(data_path: Path | str = config.DATA_PATH) -> list[Document]:
    return calculate_chunk_ids(tag_articles(split_documents(load_documents(data_path))))


# ------------------------------------------------------------------------------------------
# Vector store
# ------------------------------------------------------------------------------------------


def _client(chroma_path: Path | str):
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(path=str(chroma_path), settings=Settings(anonymized_telemetry=False))


def get_collection(chroma_path: Path | str = config.CHROMA_PATH):
    # Embeddings are computed by our own providers and passed in explicitly.
    return _client(chroma_path).get_or_create_collection(config.COLLECTION, embedding_function=None)


def clear_database(chroma_path: Path | str = config.CHROMA_PATH) -> None:
    client = _client(chroma_path)
    try:
        client.delete_collection(config.COLLECTION)
    except Exception:  # the collection didn't exist yet
        pass


@dataclass
class SyncResult:
    added: int
    deleted: int
    total: int


# progress(stage, done, total) with stage "read" (loading and splitting the PDFs) or "embed".
Progress = Callable[[str, int, int], None]


def sync_index(
    chunks: list[Document],
    chroma_path: Path | str = config.CHROMA_PATH,
    embedding_function=None,
    batch: int = 64,
    progress: Progress | None = None,
) -> SyncResult:
    collection = get_collection(chroma_path)
    stored = collection.get(include=["metadatas"])
    existing = {i: (m or {}).get("hash") for i, m in zip(stored["ids"], stored["metadatas"])}
    desired = {c.metadata["id"]: c.metadata["hash"] for c in chunks}

    to_add, to_delete = plan_sync(desired, existing)
    if to_delete:
        collection.delete(ids=to_delete)

    if to_add:
        from rag.providers import get_embedding_function

        embeddings = embedding_function or get_embedding_function()
        by_id = {c.metadata["id"]: c for c in chunks}
        new_chunks = [by_id[i] for i in to_add]
        print(f"👉 Embedding {len(new_chunks)} chunks")
        if progress:
            progress("embed", 0, len(new_chunks))
        for start in range(0, len(new_chunks), batch):
            part = new_chunks[start : start + batch]
            collection.add(
                ids=[c.metadata["id"] for c in part],
                documents=[c.page_content for c in part],
                metadatas=[
                    {k: c.metadata[k] for k in ("source", "page", "articles", "hash") if k in c.metadata} for c in part
                ],
                embeddings=embeddings.embed_documents([c.page_content for c in part]),
            )
            done = min(start + batch, len(new_chunks))
            print(f"   {done}/{len(new_chunks)}")
            if progress:
                progress("embed", done, len(new_chunks))

    result = SyncResult(added=len(to_add), deleted=len(to_delete), total=collection.count())
    print(f"✅ Index in sync: +{result.added} added, −{result.deleted} removed, {result.total} chunks in total")
    return result


def build_database(reset: bool = False, download: bool = True, progress: Progress | None = None) -> SyncResult:
    """Make the index match the PDFs in data/ (downloading the dataset first if missing)."""
    if progress:
        progress("read", 0, 0)
    if download:
        from rag.documents import download_missing

        download_missing()
    if reset:
        print("✨ Clearing database")
        clear_database()
    return sync_index(prepare_chunks(), progress=progress)
