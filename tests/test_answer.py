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
        self.result, self.queries = result, []

    def search(self, question, mode=None, k=None):
        self.queries.append(question)
        return self.result


class FakeLLM:
    def __init__(self, pieces):
        self.pieces, self.prompts, self.translations = pieces, [], []

    def complete(self, prompt):
        self.translations.append(prompt)
        return "¿Cuántas horas deben pasar entre jornadas?\n"

    def stream(self, prompt):
        self.prompts.append(prompt)
        yield from self.pieces


@pytest.fixture
def patch_pipeline(monkeypatch):
    def apply(result, pieces=("Son treinta ", "días naturales [1]", "."), llm=None):
        llm = llm or FakeLLM(list(pieces))
        retriever = FakeRetriever(result)
        monkeypatch.setattr(answer_mod, "get_retriever", lambda: retriever)
        monkeypatch.setattr(answer_mod, "_llm", lambda: llm)
        llm.retriever = retriever
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
    assert "Spanish" in prompt and "Question: ¿Cuántos días?\nAnswer in Spanish:" in prompt
    assert "in their language is" not in prompt  # no translation line


def test_answer_streams_and_records_citations(patch_pipeline):
    patch_pipeline(SearchResult([_passage(1), _passage(2)], best_relevance=0.8))
    ans, pieces = stream_answer("¿Cuántos días de vacaciones?")
    assert len(ans.passages) == 2  # sources are known before the text arrives
    assert "".join(pieces) == "Son treinta días naturales [1]."
    assert ans.text == "Son treinta días naturales [1]."
    assert [p.number for p in ans.cited] == [1]
    assert ans.grounded


def test_best_matching_passage_recovers_the_source_of_an_uncited_answer():
    vacations = _passage(1)
    vacations.text = "Artículo 38. El periodo de vacaciones anuales retribuidas no será inferior a treinta días naturales."
    trial = _passage(2)
    trial.text = "Artículo 14. El periodo de prueba no podrá exceder de seis meses para los técnicos titulados."
    answer = "Según el artículo 38, las vacaciones anuales retribuidas son de al menos treinta días naturales."
    assert answer_mod.best_matching_passage(answer, [trial, vacations]) is vacations
    assert answer_mod.best_matching_passage("Una respuesta sin relación alguna con nada", [trial, vacations]) is None


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


def test_questions_in_another_language_are_translated_for_retrieval(patch_pipeline, monkeypatch):
    monkeypatch.setattr(config, "DOC_LANGUAGE", "es")
    llm = patch_pipeline(SearchResult([_passage(1)], best_relevance=0.8))
    answer_question("How many hours must pass between two working days?")
    assert llm.retriever.queries == ["¿Cuántas horas deben pasar entre jornadas?"]  # searched in Spanish
    assert "Question: How many hours must pass between two working days?" in llm.prompts[0]  # answered as asked
    assert "English" in llm.prompts[0]
    assert "in their language is: ¿Cuántas horas deben pasar entre jornadas?" in llm.prompts[0]
    assert llm.prompts[0].rstrip().endswith("Answer in English:")  # the last word decides the language

    answer_question("¿Cuántos días de vacaciones?")  # same language as the documents: no translation
    assert llm.retriever.queries[-1] == "¿Cuántos días de vacaciones?"
    assert len(llm.translations) == 1

    monkeypatch.setattr(config, "DOC_LANGUAGE", "")
    answer_question("How many hours?")
    assert llm.retriever.queries[-1] == "How many hours?"


# ---------- The public demo keeps answering when the free quotas run out ----------


@pytest.fixture(autouse=True)
def _fresh_answer_memory():
    answer_mod.clear_stored_answers()
    yield
    answer_mod.clear_stored_answers()


class QuotaExhaustedLLM:
    """Every call fails as Gemini does when the free daily quota is used up."""

    def __init__(self):
        self.calls = 0

    def complete(self, prompt):
        from rag.providers import ApiError

        self.calls += 1
        raise ApiError("429 RESOURCE_EXHAUSTED", status=429)

    def stream(self, prompt):
        from rag.providers import ApiError

        self.calls += 1
        raise ApiError("429 RESOURCE_EXHAUSTED", status=429)
        yield  # pragma: no cover  (makes this a generator, like a real stream)


def test_with_no_model_available_the_answer_points_to_the_passages(patch_pipeline):
    patch_pipeline(SearchResult(passages=[_passage(1), _passage(2), _passage(3)], best_relevance=0.8),
                   llm=QuotaExhaustedLLM())
    answer = answer_question("¿Cuántos días de vacaciones tengo?")
    assert not answer.written_by_model and answer.grounded
    assert "límite gratuito" in answer.text
    assert [p.number for p in answer.cited] == [1, 2]  # the page highlights where the answer is


def test_an_english_question_still_works_when_the_translation_fails(patch_pipeline):
    llm = QuotaExhaustedLLM()
    patch_pipeline(SearchResult(passages=[_passage(1)], best_relevance=0.8), llm=llm)
    answer = answer_question("How many days of holiday do I get?")
    assert llm.retriever.queries == ["How many days of holiday do I get?"]  # searched untranslated
    assert "free limit" in answer.text


def test_a_question_asked_again_is_answered_without_calling_the_model(patch_pipeline):
    llm = patch_pipeline(SearchResult(passages=[_passage(1)], best_relevance=0.8))
    first = answer_question("¿Cuántos días de vacaciones tengo?")
    again = answer_question("cuántos días de vacaciones tengo")  # same question, other punctuation
    assert again.text == first.text and [p.number for p in again.cited] == [1]
    assert len(llm.prompts) == 1 and len(llm.retriever.queries) == 1


def test_an_answer_without_a_model_is_not_remembered(patch_pipeline):
    patch_pipeline(SearchResult(passages=[_passage(1)], best_relevance=0.8), llm=QuotaExhaustedLLM())
    answer_question("¿Cuántos días de vacaciones tengo?")
    assert answer_mod._ANSWERS == {}  # tomorrow, with quota again, the model will write it


def test_keyword_only_search_skips_the_similarity_gate(patch_pipeline):
    llm = patch_pipeline(SearchResult(passages=[_passage(1)], best_relevance=0.0, keyword_only=True))
    answer = answer_question("¿Cuántos días de vacaciones tengo?")
    assert answer.grounded and len(llm.prompts) == 1
