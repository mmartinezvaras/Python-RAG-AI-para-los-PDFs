"""End-to-end smoke test with the real models (LLM-as-a-judge).

Needs Ollama running with the models pulled and the index built
(`bash scripts/setup.sh` does all of it). Skipped automatically otherwise.
The full evaluation with metrics lives in eval/run_eval.py.

Run with:  pytest -m llm -v
"""

import urllib.request

import pytest

from eval.run_eval import is_abstention, judge
from rag import config
from rag.answer import answer_question


def _ollama_running() -> bool:
    try:
        urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(config.LLM_PROVIDER == "ollama" and not _ollama_running(), reason="Ollama is not running"),
]


@pytest.mark.parametrize(
    "question, expected, keywords, article",
    [
        ("¿Cuántos días de vacaciones anuales retribuidas corresponden como mínimo?", "30 días naturales", [["30", "treinta"]], "38"),
        ("¿Cuál es la duración máxima de la jornada ordinaria semanal?", "40 horas semanales", [["40", "cuarenta"]], "34"),
        ("¿Cuántas horas extraordinarias se pueden hacer como máximo al año?", "80 horas", [["80", "ochenta"]], "35"),
        # Cross-lingual: English question, Spanish document. Harder English cases are tracked in eval/.
        ("How many days of paid annual leave does a worker get?", "30 calendar days", [["30", "thirty"]], "38"),
    ],
)
def test_answers_match_the_statute(question, expected, keywords, article):
    ans = answer_question(question)
    assert ans.grounded, f"relevance gate rejected it (best {ans.best_relevance:.2f})"
    assert any(article in p.articles.split(",") for p in ans.passages), "right article not retrieved"
    # Same check as the evaluation: key figures first, the LLM judge only for paraphrases.
    assert judge(question, expected, ans.text, keywords), ans.text


def test_refuses_questions_outside_the_documents():
    ans = answer_question("¿Quién ganó el Tour de Francia en 2018?")
    assert not ans.grounded or is_abstention(ans.text), ans.text
