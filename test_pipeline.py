"""Fast tests for the indexing pipeline. No LLM or Ollama needed."""

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from populate_database import (
    add_to_chroma,
    calculate_chunk_ids,
    load_documents,
    split_documents,
)


def test_loads_sample_pdfs():
    docs = load_documents()
    sources = {d.metadata["source"].replace("\\", "/").rsplit("/", 1)[-1] for d in docs}
    assert {"football.pdf", "formula_one.pdf"} <= sources
    assert all(d.page_content.strip() for d in docs)


def test_chunks_respect_size_limit():
    chunks = split_documents(load_documents())
    assert len(chunks) > 4  # 4 pages are split into several chunks
    assert all(len(c.page_content) <= 800 for c in chunks)


def test_chunk_ids_are_deterministic_and_sequential():
    chunks = [
        Document(page_content="a", metadata={"source": "data/x.pdf", "page": 0}),
        Document(page_content="b", metadata={"source": "data/x.pdf", "page": 0}),
        Document(page_content="c", metadata={"source": "data/x.pdf", "page": 1}),
        Document(page_content="d", metadata={"source": "data/y.pdf", "page": 1}),
    ]
    ids = [c.metadata["id"] for c in calculate_chunk_ids(chunks)]
    assert ids == ["data/x.pdf:0:0", "data/x.pdf:0:1", "data/x.pdf:1:0", "data/y.pdf:1:0"]


def test_real_pdf_ids_are_relative_paths():
    chunks = calculate_chunk_ids(split_documents(load_documents()))
    assert all(c.metadata["id"].startswith("data/") for c in chunks)
    assert len({c.metadata["id"] for c in chunks}) == len(chunks)  # all unique


def test_indexing_is_incremental(tmp_path):
    """Running the indexer twice must not embed the same chunks again."""
    embeddings = DeterministicFakeEmbedding(size=64)
    chunks = split_documents(load_documents())

    first = add_to_chroma(chunks, chroma_path=str(tmp_path), embedding_function=embeddings)
    second = add_to_chroma(
        split_documents(load_documents()), chroma_path=str(tmp_path), embedding_function=embeddings
    )

    assert first == len(chunks)
    assert second == 0
