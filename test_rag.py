"""End-to-end evaluation of the RAG answers (LLM-as-a-judge).

Needs Ollama running with the models pulled and the database built
(`bash scripts/setup.sh` does all of it). Skipped automatically otherwise.

Run with:  pytest -m llm -v
"""

import re
import urllib.request

import pytest

from query_data import get_llm, query_rag


def _ollama_running() -> bool:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(not _ollama_running(), reason="Ollama is not running"),
]

EVAL_PROMPT = """
Expected Response: {expected_response}
Actual Response: {actual_response}
---
(Answer with 'true' or 'false') Does the actual response match the expected response?
"""


@pytest.mark.parametrize(
    "question, expected_response",
    [
        (
            "How many points does the winning driver get for winning a Formula One race? "
            "(Answer with the number only)",
            "25",
        ),
        ("In what year was the first Formula One season? (Answer with the year only)", "1950"),
        ("What fire-resistant material are Formula One drivers' overalls made of?", "Nomex"),
        ("How often is the FIFA World Cup held?", "Every four years"),
    ],
)
def test_answers_match_documents(question, expected_response):
    assert query_and_validate(question, expected_response)


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def query_and_validate(question: str, expected_response: str) -> bool:
    response_text = query_rag(question)

    # Cheap exact check first; fall back to the LLM judge for paraphrased answers.
    if _normalize(expected_response) in _normalize(response_text):
        return True

    prompt = EVAL_PROMPT.format(expected_response=expected_response, actual_response=response_text)
    verdict = get_llm().invoke(prompt).strip().lower()
    print(prompt)

    if "true" in verdict:
        print("\033[92m" + f"Response: {verdict}" + "\033[0m")
        return True
    if "false" in verdict:
        print("\033[91m" + f"Response: {verdict}" + "\033[0m")
        return False
    raise ValueError("Invalid evaluation result. Cannot determine if 'true' or 'false'.")
