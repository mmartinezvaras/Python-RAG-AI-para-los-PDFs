"""Precomputed document embeddings, stored in the repository next to the PDF.

Embedding the 500 chunks of the statute through an API costs 500 requests, and free tiers
allow about 1,000 a day. Without a cache, every restart of the online demo (and Streamlit
Cloud restarts it on every push) would spend half of that. With it, the demo starts without
calling the embeddings API at all; only the visitors' questions use it.

The cache is keyed by chunk ID and content hash, so a changed or new chunk is simply a miss
and gets embedded as usual. Vectors are stored as float16: plenty for cosine similarity.

    python -m rag.embedding_cache   # export the current index's embeddings for RAG_EMBED_MODEL
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from rag import config


def cache_path(model: str | None = None, data_path: Path | None = None) -> Path:
    model = model or config.EMBED_MODEL
    return Path(data_path or config.DATA_PATH) / f"embeddings-{re.sub(r'[^\w.-]', '_', model)}.npz"


def load(path: Path | None = None) -> dict[tuple[str, str], list[float]]:
    """{(chunk id, content hash): vector}; empty if there is no cache for this model."""
    path = path or cache_path()
    if not path.exists():
        return {}
    data = np.load(path, allow_pickle=False)
    vectors = data["vectors"].astype(np.float32)
    return {(i, h): v.tolist() for i, h, v in zip(data["ids"].tolist(), data["hashes"].tolist(), vectors)}


def export(chroma_path: Path | str = config.CHROMA_PATH, path: Path | None = None) -> Path:
    """Write the embeddings stored in the vector index to the cache file."""
    from rag.ingest import get_collection

    path = path or cache_path()
    stored = get_collection(chroma_path).get(include=["embeddings", "metadatas"])
    order = sorted(range(len(stored["ids"])), key=lambda i: stored["ids"][i])
    ids = np.array([stored["ids"][i] for i in order])
    hashes = np.array([(stored["metadatas"][i] or {}).get("hash", "") for i in order])
    vectors = np.array([stored["embeddings"][i] for i in order], dtype=np.float16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:  # a file object, so numpy doesn't append ".npz" to the name
        np.savez_compressed(f, ids=ids, hashes=hashes, vectors=vectors)
    print(f"💾 Saved {len(ids)} embeddings to {path} ({path.stat().st_size / 1e6:.1f} MB)")
    return path


if __name__ == "__main__":
    export()
