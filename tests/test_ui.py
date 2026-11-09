"""The HTML of the web demo: escaping, citation links, source cards and the theme CSS."""

from rag.retrieval import Passage
from ui.components import answer_card, esc, format_answer, not_found_card, sources_section
from ui.theme import DARK, LIGHT, page_css


def _p(n, articles="38", relevance=0.74, text="Artículo 38. Vacaciones anuales."):
    return Passage(f"d:{n}", text, "data/estatuto_trabajadores.pdf", 38, articles, relevance, n)


def test_text_from_pdf_or_model_cannot_inject_html_or_markdown():
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert esc("art_38 *nota* [x](y) $5") == "art&#95;38 &#42;nota&#42; &#91;x&#93;(y) &#36;5"
    html = sources_section([_p(1, text="<img src=x onerror=alert(1)>")], {}, lambda p: None)
    assert "<img" not in html


def test_pdf_line_wraps_are_undone_but_paragraphs_kept():
    from ui.components import reflow

    text = "Artículo 38. Vacaciones.\n1. El periodo de vacaciones\nanuales retribuidas.\n2. El calendario de\nla empresa.\na) Primero."
    assert reflow(text) == (
        "Artículo 38. Vacaciones.\n1. El periodo de vacaciones anuales retribuidas.\n"
        "2. El calendario de la empresa.\na) Primero."
    )


def test_citations_become_links_to_their_source():
    html = format_answer("Son **treinta días** [1][2].\n\nOtra frase.")
    assert "<strong>treinta días</strong>" in html
    assert html.count('class="lx-cite"') == 2 and 'href="#lx-src-2"' in html
    assert html.count("<p>") == 2


def test_streaming_answer_has_a_caret_and_final_one_does_not():
    assert "lx-caret" in answer_card("Son treinta", streaming=True)
    assert "lx-caret" not in answer_card("Son treinta días [1].")


def test_cited_sources_come_first_with_a_stamp_and_a_stagger_index():
    html = sources_section(
        [_p(1, "34"), _p(2, "37,38", 0.7)], {2: "cited"}, lambda p: f"https://boe.example/x.pdf#page={p.page + 1}"
    )
    assert html.index('id="lx-src-2"') < html.index('id="lx-src-1"')  # cited first
    assert html.count('class="lx-stamp') == 1 and ">Citado<" in html and "Arts.</span>37–38" in html
    assert 'style="--i:0"' in html and 'style="--i:1"' in html
    assert "Ver en el BOE, página 39" in html and "relevancia 0,70" in html
    assert 'role="heading"' in html  # not <h2>: Streamlit decorates real headings


def test_a_matching_source_gets_its_own_stamp_and_an_explanation():
    html = sources_section([_p(1), _p(2)], {2: "match"}, lambda p: None)
    assert ">Coincide<" in html and ">Citado<" not in html and "coincide con la respuesta" in html
    assert "ordenados por relevancia" in sources_section([_p(1)], {}, lambda p: None)


def test_redrawing_a_stored_answer_skips_the_entrance_motion():
    assert "lx-static" in sources_section([_p(1)], {1: "cited"}, lambda p: None, animate=False)
    assert "lx-static" not in sources_section([_p(1)], {1: "cited"}, lambda p: None)


def test_not_found_explains_why_the_model_was_not_called():
    html = not_found_card("No he encontrado información.", 0.61, 0.64)
    assert "0,61" in html and "0,64" in html and "No está en el documento" in html


def test_theme_modes():
    assert LIGHT.keys() == DARK.keys()
    paper = lambda tokens: f"--lx-paper:{tokens['paper']};"  # noqa: E731
    assert paper(DARK) in page_css("dark") and paper(LIGHT) not in page_css("dark")
    assert paper(LIGHT) in page_css("light") and paper(DARK) not in page_css("light")
    auto = page_css("auto")
    assert paper(LIGHT) in auto and "prefers-color-scheme: dark" in auto and paper(DARK) in auto
    assert "prefers-reduced-motion" in auto


def test_theme_uses_only_the_palette():
    import re

    from ui import theme

    allowed = theme.PALETTE | set(theme.DERIVED)
    for tokens in (LIGHT, DARK):
        for value in tokens.values():
            for hex_colour in re.findall(r"#[0-9A-Fa-f]{6}", value):
                assert hex_colour.upper() in allowed, hex_colour


def test_preparing_card_shows_the_current_step_and_progress():
    from ui.components import preparing_card

    reading = preparing_card("read")
    assert reading.count('class="is-now"') == 1 and "is-done" not in reading
    embedding = preparing_card("embed", 128, 512)
    assert embedding.count('class="is-done"') == 1 and "128 de 512 fragmentos" in embedding
    assert 'aria-valuenow="128"' in embedding and "width:25%" in embedding


def test_problem_card_escapes_the_message():
    from ui.components import problem_card

    html = problem_card("Error <b>429</b>")
    assert "&lt;b&gt;429" in html and 'role="alert"' in html
