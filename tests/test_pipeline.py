"""Fast tests for the indexing pipeline. No LLM or Ollama needed."""

from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

from rag import config
from rag.ingest import (
    calculate_chunk_ids,
    clean_text,
    format_articles,
    load_documents,
    plan_sync,
    prepare_chunks,
    split_documents,
    sync_index,
    tag_articles,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_sample_pdfs():
    docs = load_documents(FIXTURES)
    sources = {d.metadata["source"].rsplit("/", 1)[-1] for d in docs}
    assert {"football.pdf", "formula_one.pdf"} <= sources
    assert all(d.page_content.strip() for d in docs)
    assert all(set(d.metadata) == {"source", "page"} for d in docs)


def test_chunks_respect_size_limit():
    chunks = split_documents(load_documents(FIXTURES))
    assert len(chunks) > 4
    assert all(len(c.page_content) <= config.CHUNK_SIZE for c in chunks)


def test_clean_text_removes_boe_headers():
    page = "BOLETÍN OFICIAL DEL ESTADO\nLEGISLACIÓN CONSOLIDADA\n\n\n\nArtículo 38. Vacaciones.\nTexto\nPágina 25"
    assert clean_text(page) == "Artículo 38. Vacaciones.\nTexto"


def test_chunk_ids_are_deterministic_and_sequential():
    chunks = [
        Document(page_content="a", metadata={"source": "data/x.pdf", "page": 0}),
        Document(page_content="b", metadata={"source": "data/x.pdf", "page": 0}),
        Document(page_content="c", metadata={"source": "data/x.pdf", "page": 1}),
        Document(page_content="d", metadata={"source": "data/y.pdf", "page": 1}),
    ]
    ids = [c.metadata["id"] for c in calculate_chunk_ids(chunks)]
    assert ids == ["data/x.pdf:0:0", "data/x.pdf:0:1", "data/x.pdf:1:0", "data/y.pdf:1:0"]


def test_real_pdf_ids_are_relative_and_unique():
    chunks = prepare_chunks(FIXTURES)
    assert all(c.metadata["id"].startswith("tests/fixtures/") for c in chunks)
    assert len({c.metadata["id"] for c in chunks}) == len(chunks)


def _doc(text, source="data/ley.pdf", page=0):
    return Document(page_content=text, metadata={"source": source, "page": page})


def test_articles_are_tagged_and_inherited():
    chunks = tag_articles(
        [
            _doc("Preámbulo sin artículos."),
            _doc("Artículo 37. Descanso semanal.\nTexto del 37."),
            _doc("continúa el artículo 37 en otra página", page=1),
            _doc("final del 37.\nArtículo 38. Vacaciones anuales.\n1. Treinta días naturales.", page=1),
            _doc("Artículo 38 bis. Otro.\nTexto", page=2),
            _doc("Artículo 1. Inicio de otra ley", source="data/otra.pdf"),
        ]
    )
    assert [c.metadata["articles"] for c in chunks] == ["", "37", "37", "37,38", "38bis", "1"]


def test_table_of_contents_chunks_are_dropped():
    toc = "\n".join(f"Artículo {n}. Título {n}." for n in range(1, 8))
    chunks = tag_articles([_doc(toc), _doc("Artículo 1. Ámbito.\nTexto")])
    assert [c.metadata["articles"] for c in chunks] == ["1"]


def test_format_articles():
    assert format_articles("") == ""
    assert format_articles("38") == "Art. 38"
    assert format_articles("37,38") == "Art. 37–38"


def test_plan_sync_adds_changes_and_deletes():
    existing = {"a": "h1", "b": "h2", "c": "h3", "old": None}
    desired = {"a": "h1", "b": "CHANGED", "d": "h4", "old": "h5"}
    to_add, to_delete = plan_sync(desired, existing)
    assert sorted(to_add) == ["b", "d", "old"]  # changed, new, and stored without a hash
    assert sorted(to_delete) == ["b", "c", "old"]  # changed, removed PDF, stale


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=32)


def test_index_sync_is_incremental_and_handles_changes(tmp_path, fake_embeddings):
    chunks = prepare_chunks(FIXTURES)
    db = str(tmp_path / "chroma")

    calls = []
    first = sync_index(
        chunks, chroma_path=db, embedding_function=fake_embeddings, batch=4, progress=lambda *a: calls.append(a)
    )
    assert calls[0] == ("embed", 0, len(chunks)) and calls[-1] == ("embed", len(chunks), len(chunks))
    assert (first.added, first.deleted, first.total) == (len(chunks), 0, len(chunks))

    again = sync_index(prepare_chunks(FIXTURES), chroma_path=db, embedding_function=fake_embeddings)
    assert (again.added, again.deleted) == (0, 0)  # nothing re-embedded

    # football.pdf is deleted and one chunk of formula_one.pdf changes (new version of the PDF).
    remaining = [c for c in prepare_chunks(FIXTURES) if "football" not in c.metadata["source"]]
    n_football = len(chunks) - len(remaining)
    remaining[0].page_content += " (updated)"
    remaining = calculate_chunk_ids(remaining)

    result = sync_index(remaining, chroma_path=db, embedding_function=fake_embeddings)
    assert result.added == 1  # only the changed chunk is embedded again
    assert result.deleted == n_football + 1  # the deleted PDF + the old version of the chunk
    assert result.total == len(remaining)
