"""Hybrid retrieval: semantic (vector) search + keyword (BM25) search, fused with RRF.

Vectors are good at meaning ("¿cuántos días libres tengo al año?" → vacaciones) but weak on
exact tokens such as article numbers or figures; BM25 is the opposite. Reciprocal Rank
Fusion merges both rankings without having to calibrate their very different scores.

Every passage also carries its cosine similarity with the question, used to show relevance
and to refuse to answer when nothing in the documents is related.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from rag import config

# ------------------------------------------------------------------------------------------
# BM25
# ------------------------------------------------------------------------------------------

_STOPWORDS = set(
    """
    a al algo algun alguna algunas alguno algunos ante antes como con contra cual cuales cuando
    de del desde donde durante e el ella ellas ellos en entre era es esa esas ese eso esos esta
    estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me mi mucho muy
    nada ni no nos o os otra otras otro otros para pero poco por porque que quien se sea segun
    ser si sin sino sobre son su sus tambien tan tanto te tiene tienen todo todos tu un una unas
    uno unos y ya yo cuanto cuanta cuantos cuantas puede pueden
    the of and or to in on at for is are was were be been by with as an it its this that what
    which who how many much does do can from
    """.split()
)


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return [t for t in re.findall(r"\w+", text) if t not in _STOPWORDS and (len(t) > 1 or t.isdigit())]


class BM25:
    """Okapi BM25 (k1=1.5, b=0.75). Small and dependency-free; fine for thousands of chunks."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(d)) for d in documents]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        terms = tokenize(query)
        out = []
        for doc, length in zip(self.docs, self.lengths):
            s = 0.0
            for t in terms:
                tf = doc.get(t)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * length / (self.avg_len or 1))
                    s += self.idf[t] * tf * (self.k1 + 1) / norm
            out.append(s)
        return out

    def top(self, query: str, k: int) -> list[int]:
        scores = self.scores(query)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [i for i in ranked[:k] if scores[i] > 0]


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Merge several ranked lists of IDs. An item ranked high in any list rises to the top."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: scores[i], reverse=True)


def cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / denom) if denom else 0.0


# ------------------------------------------------------------------------------------------
# Retriever
# ------------------------------------------------------------------------------------------


@dataclass
class Passage:
    id: str
    text: str
    source: str
    page: int | None
    articles: str
    relevance: float  # cosine similarity with the question
    number: int = 0  # [n] used in the prompt and in the citations


@dataclass
class SearchResult:
    passages: list[Passage] = field(default_factory=list)
    best_relevance: float = 0.0  # best cosine similarity among all candidates


class Retriever:
    def __init__(self, collection=None, embedding_function=None):
        from rag.ingest import get_collection
        from rag.providers import get_embedding_function

        self.collection = collection if collection is not None else get_collection()
        self.embeddings = embedding_function or get_embedding_function()
        self._corpus_size = -1

    def _load_corpus(self) -> None:
        """(Re)build the BM25 index when the vector store changed size (e.g. a PDF was added)."""
        size = self.collection.count()
        if size == self._corpus_size:
            return
        data = self.collection.get(include=["documents", "metadatas"])
        self.ids: list[str] = data["ids"]
        self.texts = dict(zip(data["ids"], data["documents"]))
        self.metas = dict(zip(data["ids"], data["metadatas"]))
        self.bm25 = BM25(data["documents"])
        self._corpus_size = size

    def search(self, query: str, k: int = config.TOP_K, mode: str = config.RETRIEVAL_MODE) -> SearchResult:
        self._load_corpus()
        if not self.ids:
            return SearchResult()

        q_vec = self.embeddings.embed_query(query)
        n = min(config.CANDIDATES, len(self.ids))
        res = self.collection.query(query_embeddings=[q_vec], n_results=n, include=["embeddings"])
        vector_ids = res["ids"][0]
        relevance = {i: cosine(q_vec, e) for i, e in zip(vector_ids, res["embeddings"][0])}

        if mode == "hybrid":
            keyword_ids = [self.ids[i] for i in self.bm25.top(query, n)]
            ranked = reciprocal_rank_fusion([vector_ids, keyword_ids])[:k]
            missing = [i for i in ranked if i not in relevance]
            if missing:
                extra = self.collection.get(ids=missing, include=["embeddings"])
                relevance.update({i: cosine(q_vec, e) for i, e in zip(extra["ids"], extra["embeddings"])})
        else:
            ranked = vector_ids[:k]

        passages = []
        for number, pid in enumerate(ranked, start=1):
            meta = self.metas.get(pid) or {}
            passages.append(
                Passage(
                    id=pid,
                    text=self.texts.get(pid, ""),
                    source=meta.get("source", pid.rsplit(":", 2)[0]),
                    page=meta.get("page"),
                    articles=meta.get("articles", ""),
                    relevance=relevance.get(pid, 0.0),
                    number=number,
                )
            )
        return SearchResult(passages=passages, best_relevance=max(relevance.values(), default=0.0))
