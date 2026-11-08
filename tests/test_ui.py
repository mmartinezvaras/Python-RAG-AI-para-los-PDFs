"""The HTML of the web demo: escaping, citation links, source cards and the theme CSS."""

from rag.retrieval import Passage
from ui.components import answer_card, esc, format_answer, not_found_card, sources_section
from ui.theme import DARK, LIGHT, page_css


def _p(n, articles="38", relevance=0.74, text="Artículo 38. Vacaciones anuales."):
    return Passage(f"d:{n}", text, "data/estatuto_trabajadores.pdf", 38, articles, relevance, n)


def test_text_from_pdf_or_model_cannot_inject_html_or_markdown():
    assert esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert esc("art_38 *nota* [x](y) $5") == "art&#95;38 &#42;nota&#42; &#91;x&#93;(y) &#36;5"
    html = sources_section([_p(1, text="<img src=x onerror=alert(1)>")], [], lambda p: None)
    assert "<img" not in html


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
        [_p(1, "34"), _p(2, "37,38", 0.7)], [2], lambda p: f"https://boe.example/x.pdf#page={p.page + 1}"
    )
    assert html.index('id="lx-src-2"') < html.index('id="lx-src-1"')  # cited first
    assert html.count("lx-stamp") == 1 and "Arts.</span>37–38" in html
    assert 'style="--i:0"' in html and 'style="--i:1"' in html
    assert "Ver en el BOE, página 39" in html and "relevancia 0,70" in html
    assert 'role="heading"' in html  # not <h2>: Streamlit decorates real headings


def test_redrawing_a_stored_answer_skips_the_entrance_motion():
    assert "lx-static" in sources_section([_p(1)], [1], lambda p: None, animate=False)
    assert "lx-static" not in sources_section([_p(1)], [1], lambda p: None)


def test_not_found_explains_why_the_model_was_not_called():
    html = not_found_card("No he encontrado información.", 0.61, 0.64)
    assert "0,61" in html and "0,64" in html and "No está en el documento" in html


def test_theme_modes():
    assert LIGHT.keys() == DARK.keys()
    assert DARK["paper"] in page_css("dark") and LIGHT["paper"] not in page_css("dark")
    assert LIGHT["paper"] in page_css("light") and DARK["paper"] not in page_css("light")
    auto = page_css("auto")
    assert LIGHT["paper"] in auto and "prefers-color-scheme: dark" in auto and DARK["paper"] in auto
    assert "prefers-reduced-motion" in auto
