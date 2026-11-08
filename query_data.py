"""Ask a question about the indexed PDFs from the command line (the answer is streamed).

Usage:
    python query_data.py "¿Cuántos días de vacaciones me corresponden al año?"
    python query_data.py --mode vector "How many hours is the maximum working week?"
"""

import argparse
import sys

from rag.answer import passage_label, stream_answer


def query_rag(question: str, mode: str | None = None) -> str:
    kwargs = {"mode": mode} if mode else {}
    answer, pieces = stream_answer(question, **kwargs)
    print("Response: ", end="", flush=True)
    for piece in pieces:
        print(piece, end="", flush=True)
    print()
    if answer.passages:
        cited = {p.number for p in answer.cited}
        print("Sources:")
        for p in answer.passages:
            mark = "✔" if p.number in cited else " "
            print(f"  {mark} [{p.number}] {passage_label(p)}  (relevance {p.relevance:.2f})  {p.id}")
    else:
        print(f"(No passage was relevant enough: best similarity {answer.best_relevance:.2f})")
    return answer.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question", type=str)
    parser.add_argument("--mode", choices=["hybrid", "vector"], default=None)
    args = parser.parse_args()
    query_rag(args.question, args.mode)


if __name__ == "__main__":
    sys.exit(main())
