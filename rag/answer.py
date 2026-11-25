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
from rag.retrieval import Passage, Retriever, SearchResult, tokenize

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

# When no model can write the answer (every free quota used up), the search still works: point
# the visitor to the passages that answer the question, which the page shows with their article.
NO_MODEL = {
    "es": (
        "El asistente de IA ha llegado por hoy a su límite gratuito, así que no puedo redactar la respuesta. "
        "Lo que dice la ley sobre tu pregunta está en {refs}: lo tienes justo debajo, con su artículo y su página."
    ),
    "en": (
        "The AI assistant has reached its free limit for today, so I can't write the answer. "
        "What the law says about your question is in {refs}: you'll find it right below, with its article and page."
    ),
}

_SPANISH_CHARS = re.compile(r"[¿¡ñáéíóúü]", re.IGNORECASE)
# Short, very common words that tell the two languages apart. Visitors often write without
# accents or the opening "¿" ("pone algo de la jubilacion?"), so the words matter more than marks.
_SPANISH_WORDS = set(
    "que qué cuanto cuantos cuantas cuál cual como cómo donde dónde cuando cuándo puede pueden tengo "
    "los las del para por de la el en y con se me mi mis hay algo pone dice si es son al lo un una "
    "sobre trabajador trabajadora empresa contrato dias días horas despido jubilacion jubilación edad "
    "vacaciones salario permiso año ano paga jornada excedencia baja nomina nómina indemnizacion".split()
)
_ENGLISH_WORDS = set(
    "the what how many much is are do does did can could my i of to in for about when where which "
    "who after before have has get worker workers company contract days hours dismissal law age "
    "retirement holiday holidays leave pay salary overtime notice severance year per paid unfair".split()
)


def detect_language(text: str) -> str:
    """'es' or 'en'. The documents and most visitors are Spanish, so a question only counts as
    English when its words clearly are; a tie (or a single word like "vacaciones?") is Spanish."""
    if _SPANISH_CHARS.search(text):
        return "es"
    words = re.findall(r"[a-záéíóúüñ]+", text.lower())
    spanish = sum(w in _SPANISH_WORDS for w in words)
    english = sum(w in _ENGLISH_WORDS for w in words)
    return "en" if english > spanish else "es"


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
    written_by_model: bool = True  # False when no model could answer and we point to the passages

    @property
    def sources(self) -> list[str]:
        return [p.id for p in self.passages]

    @property
    def cited(self) -> list[Passage]:
        by_number = {p.number: p for p in self.passages}
        return [by_number[n] for n in cited_numbers(self.text) if n in by_number]

    @property
    def matching(self) -> Passage | None:
        """When the model gave no [n] citations: the passage whose wording the answer follows."""
        return best_matching_passage(self.text, self.passages)


def best_matching_passage(answer_text: str, passages: list[Passage], min_overlap: float = 0.5) -> Passage | None:
    """The passage that shares most of the answer's content words (at least ``min_overlap`` of
    them). Small models often answer correctly but forget the [n] markers; this recovers which
    passage the answer came from without asking the model again."""
    words = set(tokenize(re.sub(r"\[\d+\]", " ", answer_text)))
    if not words or not passages:
        return None
    scored = [(len(words & set(tokenize(p.text))) / len(words), -p.number, p) for p in passages]
    score, _, best = max(scored, key=lambda t: (t[0], t[1]))
    return best if score >= min_overlap else None


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
    from rag.providers import ApiError

    try:
        translated = _llm().complete(TRANSLATE_PROMPT.format(target=_LANGUAGE_NAMES[target], question=question))
    except ApiError:
        return question  # the semantic search also matches across languages, only a bit worse
    translated = translated.strip().strip('"').splitlines()[0].strip() if translated.strip() else ""
    return translated or question


def no_model_text(question: str, passages: list[Passage]) -> str:
    numbers = [f"[{p.number}]" for p in passages[:2]]
    joiner = " y " if detect_language(question) == "es" else " and "
    return NO_MODEL[detect_language(question)].format(refs=joiner.join(numbers))


# Answers already written, shared by every visitor of this server: a question asked again (the
# example buttons, above all) is answered without spending the model's quota.
_ANSWERS: dict[tuple[str, str], RagAnswer] = {}
MAX_STORED_ANSWERS = 500


def _answer_key(question: str, mode: str) -> tuple[str, str]:
    return " ".join(re.sub(r"[¿?¡!.,;:]", " ", question.lower()).split()), mode


def clear_stored_answers() -> None:
    _ANSWERS.clear()


def retrieve(question: str, mode: str = config.RETRIEVAL_MODE, query: str | None = None) -> SearchResult:
    return get_retriever().search(query or search_query(question), mode=mode)


def stream_answer(question: str, mode: str = config.RETRIEVAL_MODE) -> tuple[RagAnswer, Iterator[str]]:
    """Start answering. Returns the answer object (passages already filled) and a generator
    of text pieces; when the generator is exhausted, ``answer.text`` holds the full text.

    It always answers, even with the models out of quota: a question already answered comes
    from memory, the search falls back to keywords if the question can't be embedded, and if no
    model can write, the answer points to the passages that hold it (``written_by_model``)."""
    key = _answer_key(question, mode)
    if key in _ANSWERS:
        stored = _ANSWERS[key]
        answer = RagAnswer(
            question=question,
            text=stored.text,
            passages=stored.passages,
            best_relevance=stored.best_relevance,
            grounded=stored.grounded,
        )
        return answer, iter([answer.text])

    query = search_query(question)
    result = retrieve(question, mode, query=query)
    answer = RagAnswer(question=question, passages=result.passages, best_relevance=result.best_relevance)

    # Without a vector there's no similarity: the keyword search already left out passages that
    # share no word with the question, and the prompt tells the model to say when it isn't there.
    off_topic = result.best_relevance < config.MIN_RELEVANCE and not result.keyword_only
    if not result.passages or off_topic:
        answer.grounded = False
        answer.text = NOT_FOUND[detect_language(question)]
        answer.passages = []
        _remember(key, answer)
        return answer, iter([answer.text])

    prompt = build_prompt(question, result.passages, translated=query)

    def generate() -> Iterator[str]:
        from rag.providers import ApiError

        pieces = []
        try:
            for piece in _llm().stream(prompt):
                pieces.append(piece)
                yield piece
        except ApiError:
            if pieces:  # cut off half-way: keep what arrived
                answer.text = "".join(pieces).strip()
                return
            answer.written_by_model = False
            answer.text = no_model_text(question, answer.passages)
            yield answer.text
            return
        answer.text = "".join(pieces).strip()
        if answer.text and not result.keyword_only:
            _remember(key, answer)

    return answer, generate()


def _remember(key: tuple[str, str], answer: RagAnswer) -> None:
    if len(_ANSWERS) >= MAX_STORED_ANSWERS:
        _ANSWERS.pop(next(iter(_ANSWERS)))  # forget the oldest
    _ANSWERS[key] = answer


def answer_question(question: str, mode: str = config.RETRIEVAL_MODE) -> RagAnswer:
    answer, pieces = stream_answer(question, mode)
    for _ in pieces:
        pass
    return answer
