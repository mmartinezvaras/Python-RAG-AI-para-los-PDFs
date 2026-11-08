"""Retrieval building blocks: tokenizer, BM25, rank fusion, and the hybrid retriever."""

from langchain_core.documents import Document

from rag.ingest import calculate_chunk_ids, sync_index, tag_articles
from rag.retrieval import BM25, Retriever, cosine, reciprocal_rank_fusion, tokenize


def test_tokenize_lowercases_strips_accents_and_stopwords():
    assert tokenize("¿Cuántos días de VACACIONES tiene el trabajador? Artículo 38") == [
        "dias",
        "vacaciones",
        "trabajador",
        "articulo",
        "38",
    ]


def test_bm25_ranks_the_document_with_the_rare_term_first():
    docs = [
        "El salario se abona mensualmente.",
        "Las vacaciones anuales retribuidas serán de treinta días naturales.",
        "El periodo de prueba no podrá exceder de seis meses.",
    ]
    bm25 = BM25(docs)
    assert bm25.top("¿Cuántos días de vacaciones?", k=3)[0] == 1
    assert bm25.top("tour de francia", k=3) == []  # no shared terms → nothing returned


def test_reciprocal_rank_fusion_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["d", "b", "e"]])
    assert fused[0] == "b"  # 2nd in both lists beats 1st in only one
    assert set(fused) == {"a", "b", "c", "d", "e"}


def test_cosine():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert abs(cosine([1, 0], [0, 1])) < 1e-9
    assert cosine([0, 0], [1, 1]) == 0.0


class KeywordEmbeddings:
    """Tiny deterministic embedding: one dimension per vocabulary word (bag of words)."""

    VOCAB = ["vacaciones", "dias", "salario", "prueba", "meses", "jornada", "horas", "despido"]

    def _vec(self, text):
        tokens = tokenize(text)
        return [float(tokens.count(w)) + 0.01 for w in self.VOCAB]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def test_hybrid_retriever_returns_numbered_passages_with_relevance(tmp_path):
    texts = [
        "Artículo 38. Vacaciones anuales.\nLas vacaciones serán de treinta días naturales.",
        "Artículo 14. Periodo de prueba.\nNo podrá exceder de seis meses para técnicos titulados.",
        "Artículo 34. Jornada.\nLa jornada será de cuarenta horas semanales.",
        "Artículo 29. Salario.\nEl salario se liquida mensualmente.",
    ]
    chunks = calculate_chunk_ids(
        tag_articles([Document(page_content=t, metadata={"source": "data/ley.pdf", "page": i}) for i, t in enumerate(texts)])
    )
    emb = KeywordEmbeddings()
    sync_index(chunks, chroma_path=str(tmp_path), embedding_function=emb)

    from rag.ingest import get_collection

    retriever = Retriever(collection=get_collection(str(tmp_path)), embedding_function=emb)
    for mode in ("hybrid", "vector"):
        result = retriever.search("¿Cuántos días de vacaciones tengo?", k=2, mode=mode)
        top = result.passages[0]
        assert top.articles == "38" and top.number == 1 and top.page == 0
        assert top.relevance == result.best_relevance > 0.9
        assert [p.number for p in result.passages] == [1, 2]
