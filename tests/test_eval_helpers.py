"""The answer-checking helpers used by the evaluation."""

from eval.run_eval import is_abstention, keyword_match


def test_keyword_match_numbers_are_whole_numbers():
    assert keyword_match("Corresponden 30 días naturales [1].", [["30", "treinta"], ["natural"]])
    assert keyword_match("Treinta días naturales.", [["30", "treinta"], ["natural"]])
    assert not keyword_match("Son 300 días naturales.", [["30"]])
    assert not keyword_match("Son 15 días [1].", [["1"]])  # citations don't count as facts


def test_keyword_match_words_match_as_prefixes_and_ignore_accents():
    assert keyword_match("Seis meses como máximo.", [["6", "seis"], ["mes"]])
    assert keyword_match("veinte días HÁBILES", [["habil"]])
    assert not keyword_match("anything", None)


def test_is_abstention():
    assert is_abstention("No he encontrado información sobre esto en los documentos.")
    assert is_abstention("The documents don't include that information.")
    assert not is_abstention("Corresponden 30 días naturales de vacaciones [1].")
