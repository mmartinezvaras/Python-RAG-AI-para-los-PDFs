"""Answering: retrieve → relevance gate → grounded prompt with numbered passages → LLM.

The model must cite the passages it uses as [1], [2]... so every sentence of the answer can
be traced to a page of the PDF. If no passage is related to the question (low cosine
similarity), we don't call the model at all: nothing to ground an answer on.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache

from rag import config
from rag.ingest import format_articles
from rag.retrieval import Passage, Retriever, SearchResult

PROMPT_TEMPLATE = """You answer questions using ONLY the numbered passages below.

Rules:
- Use only facts stated in the passages. Do not use outside knowledge.
- After each fact, cite the passage(s) it comes from with their number in square brackets, e.g. [1] or [2][3].
- If the passages do not contain the answer, say that the documents don't include that information, and nothing else.
- Answer in the same language as the question ({language}). Be concise: one to four sentences.

Passages:
{context}

{translation}Question: {question}
Answer in {language}:"""

NOT_FOUND = {
    "es": "No he encontrado información sobre esto en los documentos.",
    "en": "I couldn't find information about this in the documents.",
}

_SPANISH_HINTS = re.compile(
    r"[¿¡ñáéíóú]|\b(qué|que|cuántos?|cuántas?|cuál|cómo|dónde|cuando|cuándo|puede|tengo|los|las|del|para|por)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    return "es" if _SPANISH_HINTS.search(text) else "en"


def passage_label(p: Passage) -> str:
    parts = [p.source.rsplit("/", 1)[-1]]
    if p.page is not None:
        parts.append(f"p. {int(p.page) + 1}")
    if p.articles:
        parts.append(format_articles(p.articles))
    return " · ".join(parts)


def build_prompt(question: str, passages: list[Passage], translated: str | None = None) -> str:
    """``translated``: the question in the documents' language, when it was asked in another
    one. Small models match the passages much better with both versions in front of them."""
    context = "\n\n".join(f"[{p.number}] ({passage_label(p)})\n{p.text}" for p in passages)
    language = "Spanish" if detect_language(question) == "es" else "English"
    extra = ""
    if translated and translated != question:
        extra = f"(For matching the passages, the question in their language is: {translated})\n"
    return PROMPT_TEMPLATE.format(context=context, question=question, translation=extra, language=language)


def cited_numbers(text: str) -> list[int]:
    """Passage numbers cited in the answer, in order of first appearance: '[2][1] … [2]' → [2, 1]."""
    seen: list[int] = []
    for n in re.findall(r"\[(\d+)\]", text):
        if int(n) not in seen:
            seen.append(int(n))
    return seen


@dataclass
class RagAnswer:
    question: str
    text: str = ""
    passages: list[Passage] = field(default_factory=list)
    best_relevance: float = 0.0
    grounded: bool = True  # False when the relevance gate stopped us before the LLM

    @property
    def sources(self) -> list[str]:
        return [p.id for p in self.passages]

    @property
    def cited(self) -> list[Passage]:
        by_number = {p.number: p for p in self.passages}
        return [by_number[n] for n in cited_numbers(self.text) if n in by_number]


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    return Retriever()


@lru_cache(maxsize=1)
def _llm():
    from rag.providers import get_llm

    return get_llm()


TRANSLATE_PROMPT = """Translate this question into {target}. Keep legal and technical terms precise.
Reply with the translated question only, no quotes and no explanations.

Question: {question}"""

_LANGUAGE_NAMES = {"es": "Spanish", "en": "English"}


def search_query(question: str) -> str:
    """The text used for retrieval: the question itself, or its translation into the
    documents' language when it is asked in another language (cross-lingual retrieval)."""
    target = config.DOC_LANGUAGE
    if not target or detect_language(question) == target or target not in _LANGUAGE_NAMES:
        return question
    translated = _llm().complete(TRANSLATE_PROMPT.format(target=_LANGUAGE_NAMES[target], question=question))
    translated = translated.strip().strip('"').splitlines()[0].strip() if translated.strip() else ""
    return translated or question


def retrieve(question: str, mode: str = config.RETRIEVAL_MODE, query: str | None = None) -> SearchResult:
    return get_retriever().search(query or search_query(question), mode=mode)


def stream_answer(question: str, mode: str = config.RETRIEVAL_MODE) -> tuple[RagAnswer, Iterator[str]]:
    """Start answering. Returns the answer object (passages already filled) and a generator
    of text pieces; when the generator is exhausted, ``answer.text`` holds the full text."""
    query = search_query(question)
    result = retrieve(question, mode, query=query)
    answer = RagAnswer(question=question, passages=result.passages, best_relevance=result.best_relevance)

    if not result.passages or result.best_relevance < config.MIN_RELEVANCE:
        answer.grounded = False
        answer.text = NOT_FOUND[detect_language(question)]
        answer.passages = []
        return answer, iter([answer.text])

    prompt = build_prompt(question, result.passages, translated=query)

    def generate() -> Iterator[str]:
        pieces = []
        for piece in _llm().stream(prompt):
            pieces.append(piece)
            yield piece
        answer.text = "".join(pieces).strip()

    return answer, generate()


def answer_question(question: str, mode: str = config.RETRIEVAL_MODE) -> RagAnswer:
    answer, pieces = stream_answer(question, mode)
    for _ in pieces:
        pass
    return answer
