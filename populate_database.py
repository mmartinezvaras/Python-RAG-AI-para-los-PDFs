"""Index the PDFs in data/ (downloading the default dataset if missing).

Usage:
    python populate_database.py          # sync: add new/changed chunks, remove deleted ones
    python populate_database.py --reset  # rebuild from scratch (needed after changing the embedding model)
"""

import argparse

from rag.ingest import build_database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Rebuild the index from scratch.")
    parser.add_argument("--no-download", action="store_true", help="Don't download the default dataset.")
    args = parser.parse_args()
    build_database(reset=args.reset, download=not args.no_download)


if __name__ == "__main__":
    main()
