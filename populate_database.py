"""Index the PDFs in data/ into a persistent Chroma vector store.

Usage:
    python populate_database.py          # add only new chunks (incremental)
    python populate_database.py --reset  # rebuild from scratch
"""

import argparse
import os
import shutil

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from get_embedding_function import get_embedding_function

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma")
DATA_PATH = os.path.join(BASE_DIR, "data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset the database.")
    args = parser.parse_args()
    build_database(reset=args.reset)


def build_database(reset: bool = False) -> int:
    """Load, split and index the PDFs. Returns the number of chunks added."""
    if reset:
        print("✨ Clearing Database")
        clear_database()

    documents = load_documents()
    chunks = split_documents(documents)
    return add_to_chroma(chunks)


def load_documents(data_path: str = DATA_PATH) -> list[Document]:
    document_loader = PyPDFDirectoryLoader(data_path)
    return document_loader.load()


def split_documents(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=80,
        length_function=len,
        is_separator_regex=False,
    )
    return text_splitter.split_documents(documents)


def add_to_chroma(
    chunks: list[Document], chroma_path: str = CHROMA_PATH, embedding_function=None
) -> int:
    db = Chroma(
        persist_directory=chroma_path,
        embedding_function=embedding_function or get_embedding_function(),
    )

    chunks_with_ids = calculate_chunk_ids(chunks)

    # Only embed chunks whose ID is not stored yet (incremental indexing).
    existing_items = db.get(include=[])  # IDs are always included by default
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB: {len(existing_ids)}")

    new_chunks = [c for c in chunks_with_ids if c.metadata["id"] not in existing_ids]

    if new_chunks:
        print(f"👉 Adding new documents: {len(new_chunks)}")
        db.add_documents(new_chunks, ids=[c.metadata["id"] for c in new_chunks])
    else:
        print("✅ No new documents to add")
    return len(new_chunks)


def calculate_chunk_ids(chunks: list[Document]) -> list[Document]:
    # Creates IDs like "data/formula_one.pdf:1:2"
    # Page Source : Page Number : Chunk Index
    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source", "")
        if os.path.isabs(source):
            source = os.path.relpath(source, BASE_DIR)
        source = source.replace(os.sep, "/")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        chunk.metadata["id"] = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

    return chunks


def clear_database(chroma_path: str = CHROMA_PATH):
    if os.path.exists(chroma_path):
        shutil.rmtree(chroma_path)


if __name__ == "__main__":
    main()
