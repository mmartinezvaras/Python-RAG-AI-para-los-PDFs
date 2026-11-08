"""Answer generation logic with a fake retriever and a fake LLM (no models needed)."""

import pytest

from rag import answer as answer_mod
from rag import config
from rag.answer import answer_question, build_prompt, cited_numbers, detect_language, stream_answer
from rag.retrieval import Passage, SearchResult


def _passage(n, relevance=0.8, articles="38"):
    return Passage(
        id=f"data/estatuto_trabajadores.pdf:{n}:0",
        text=f"texto del fragmento {n}",
        source="data/estatuto_trabajadores.pdf",
        page=n,
        articles=articles,
        relevance=relevance,
        number=n,
    )


class FakeRetriever:
    def __init__(self, result):
        self.result = result

    def search(self, question, mode=None, k=None):
        return self.result


class FakeLLM:
    def __init__(self, pieces):
        self.pieces, self.prompts = pieces, []

    def stream(self, prompt):
        self.prompts.append(prompt)
        yield from self.pieces


@pytest.fixture
def patch_pipeline(monkeypatch):
    def apply(result, pieces=("Son treinta ", "días naturales [1]", "."), llm=None):
        llm = llm or FakeLLM(list(pieces))
        monkeypatch.setattr(answer_mod, "get_retriever", lambda: FakeRetriever(result))
        monkeypatch.setattr(answer_mod, "_llm", lambda: llm)
        return llm

    return apply


def test_detect_language():
    assert detect_language("¿Cuántos días de vacaciones tengo?") == "es"
    assert detect_language("How many holidays do I get?") == "en"


def test_cited_numbers_in_order_without_duplicates():
    assert cited_numbers("A [2][1]. B [2]. C [10].") == [2, 1, 10]
    assert cited_numbers("sin citas") == []


def test_prompt_numbers_and_labels_the_passages():
    prompt = build_prompt("¿Cuántos días?", [_passage(1), _passage(2, articles="37,38")])
    assert "[1] (estatuto_trabajadores.pdf · p. 2 · Art. 38)" in prompt
    assert "[2] (estatuto_trabajadores.pdf · p. 3 · Art. 37–38)" in prompt
    assert "Spanish" in prompt and "Question: ¿Cuántos días?" in prompt


def test_answer_streams_and_records_citations(patch_pipeline):
    patch_pipeline(SearchResult([_passage(1), _passage(2)], best_relevance=0.8))
    ans, pieces = stream_answer("¿Cuántos días de vacaciones?")
    assert len(ans.passages) == 2  # sources are known before the text arrives
    assert "".join(pieces) == "Son treinta días naturales [1]."
    assert ans.text == "Son treinta días naturales [1]."
    assert [p.number for p in ans.cited] == [1]
    assert ans.grounded


def test_low_relevance_skips_the_llm(patch_pipeline):
    llm = patch_pipeline(SearchResult([_passage(1, relevance=0.1)], best_relevance=config.MIN_RELEVANCE - 0.01))
    ans = answer_question("¿Quién ganó el Tour de Francia en 2018?")
    assert not ans.grounded and ans.passages == []
    assert ans.text == answer_mod.NOT_FOUND["es"]
    assert llm.prompts == []  # the model was never called

    ans_en = answer_question("Who won the 2018 Tour de France?")
    assert ans_en.text == answer_mod.NOT_FOUND["en"]


def test_empty_index_says_not_found(patch_pipeline):
    patch_pipeline(SearchResult())
    assert not answer_question("¿Algo?").grounded
