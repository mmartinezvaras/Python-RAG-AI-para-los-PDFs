"""Ask a question about the indexed PDFs.

Usage:
    python query_data.py "How many points does a race winner get in Formula One?"
"""

import argparse
import os
from dataclasses import dataclass, field

from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import OllamaLLM

from get_embedding_function import get_embedding_function
from populate_database import CHROMA_PATH

LLM_MODEL = os.getenv("RAG_LLM_MODEL", "llama3.2:3b")
TOP_K = 5

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}

If the context does not contain the answer, say that you don't know.
Answer in the same language as the question.
"""


@dataclass
class RagAnswer:
    text: str
    sources: list[str] = field(default_factory=list)
    passages: list[str] = field(default_factory=list)


def get_llm():
    return OllamaLLM(model=LLM_MODEL, temperature=0)


def answer_question(query_text: str) -> RagAnswer:
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embedding_function())

    results = db.similarity_search_with_score(query_text, k=TOP_K)

    context_text = "\n\n---\n\n".join(doc.page_content for doc, _score in results)
    prompt = ChatPromptTemplate.from_template(PROMPT_TEMPLATE).format(
        context=context_text, question=query_text
    )

    response_text = get_llm().invoke(prompt).strip()

    return RagAnswer(
        text=response_text,
        sources=[doc.metadata.get("id") for doc, _score in results],
        passages=[doc.page_content for doc, _score in results],
    )


def query_rag(query_text: str) -> str:
    answer = answer_question(query_text)
    print(f"Response: {answer.text}\nSources: {answer.sources}")
    return answer.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_rag(args.query_text)


if __name__ == "__main__":
    main()
