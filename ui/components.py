"""HTML for the parts of the demo that Streamlit widgets can't express well: the streamed
answer with clickable citations, the source cards with their article, relevance and "Citado"
stamp, and the loading / not-found states. Pure functions, so they are unit-tested.

Everything that comes from the PDF or the model is escaped before it reaches the page.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

from rag.retrieval import Passage


def icon(name: str, cls: str = "") -> str:
    """A Material Symbols icon (decorative, hidden from screen readers)."""
    return f'<span class="ms {cls}" aria-hidden="true">{name}</span>'


def _decimal(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


# Streamlit runs st.markdown text through a Markdown parser even inside raw HTML, so besides
# the HTML special characters we neutralise Markdown syntax (*, _, [, $ for LaTeX…) in any
# text that comes from the PDF or the model.
_ENTITIES = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    "*": "&#42;", "_": "&#95;", "`": "&#96;", "[": "&#91;", "]": "&#93;",
    "~": "&#126;", "$": "&#36;", "#": "&#35;", "|": "&#124;", "\\": "&#92;",
}


def esc(text: str) -> str:
    return "".join(_ENTITIES.get(ch, ch) for ch in text)


def format_answer(text: str) -> str:
    """Escape the model's text, keep **bold**, paragraphs and line breaks, and turn [n] into
    links that jump to source n."""
    out: list[str] = []
    for part in re.split(r"(\*\*.+?\*\*|\[\d+\])", text.strip()):
        if re.fullmatch(r"\*\*.+\*\*", part, re.S):
            out.append(f"<strong>{esc(part[2:-2])}</strong>")
        elif re.fullmatch(r"\[\d+\]", part):
            n = part[1:-1]
            if out:
                out[-1] = out[-1].rstrip(" ")
            out.append(f'<a class="lx-cite" href="#lx-src-{n}" title="Ver la fuente {n}" aria-label="Fuente {n}">{n}</a>')
        else:
            out.append(esc(part))
    safe = "".join(out)
    paragraphs = [p.replace("\n", "<br>") for p in re.split(r"\n\s*\n", safe) if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def answer_card(text: str, streaming: bool = False) -> str:
    caret = '<span class="lx-caret" aria-hidden="true"></span>' if streaming else ""
    body = format_answer(text) if text.strip() else "<p></p>"
    if caret:  # put the caret right after the last word
        body = body[: -len("</p>")] + caret + "</p>"
    state = ' aria-busy="true"' if streaming else ""
    return (
        f'<section class="lx-answer" aria-live="polite"{state}>'
        f'<div class="lx-h" role="heading" aria-level="2">{icon("balance")}Respuesta</div>'
        f'<div class="lx-answer-body">{body}</div>'
        "</section>"
    )


def searching_card(chunk_count: int) -> str:
    lines = "".join('<span class="lx-skel"></span>' for _ in range(3))
    return (
        '<section class="lx-answer lx-searching" aria-live="polite" aria-busy="true">'
        f'<div class="lx-h" role="heading" aria-level="2">{icon("manage_search", "lx-spin")}Buscando en {chunk_count} fragmentos del Estatuto…</div>'
        f'<div class="lx-skel-wrap">{lines}</div>'
        "</section>"
    )


def not_found_card(text: str, best_relevance: float, threshold: float) -> str:
    return (
        '<section class="lx-answer lx-notfound" aria-live="polite">'
        f'<div class="lx-h" role="heading" aria-level="2">{icon("search_off")}No está en el documento</div>'
        f'<div class="lx-answer-body"><p>{esc(text)}</p></div>'
        f'<p class="lx-note">Ningún fragmento se parecía lo bastante a la pregunta (similitud máxima '
        f"{_decimal(best_relevance)}, umbral {_decimal(threshold)}), así que no se ha llamado al modelo: "
        "sin texto en el que apoyarse, solo podría inventar.</p>"
        "</section>"
    )


def _article_label(articles: str) -> tuple[str, str]:
    parts = [a for a in articles.split(",") if a]
    if not parts:
        return "", ""
    return ("Art.", parts[0]) if len(parts) == 1 else ("Arts.", f"{parts[0]}–{parts[-1]}")


STAMPS = {
    "cited": ("Citado", "Fuente citada en la respuesta"),
    "match": ("Coincide", "El texto de esta fuente coincide con la respuesta"),
}


def source_card(p: Passage, mark: str | None, link: str | None, index: int = 0) -> str:
    """``mark``: "cited" (the model cited it), "match" (the answer follows its wording) or None."""
    prefix, number = _article_label(p.articles)
    page = f"página {int(p.page) + 1}" if p.page is not None else ""
    if number:
        margin = f'<span class="lx-art"><span class="lx-art-pre">{prefix}</span>{esc(number)}</span>'
    else:
        margin = f'<span class="lx-art lx-art-file">{icon("description")}</span>'
    meter = max(0.0, min(1.0, (p.relevance - 0.4) / 0.5))  # 0.40 → empty, 0.90 → full
    filename = esc(p.source.rsplit("/", 1)[-1])
    boe = (
        f'<a class="lx-boe" href="{esc(link)}" target="_blank" rel="noopener">'
        f"{icon('open_in_new')}Ver en el BOE, {page}</a>"
        if link
        else ""
    )
    stamp = ""
    if mark in STAMPS:
        label, aria = STAMPS[mark]
        stamp = f'<span class="lx-stamp lx-stamp-{mark}" aria-label="{aria}">{label}</span>'
    return (
        f'<article class="lx-src{" is-cited" if mark else ""}" id="lx-src-{p.number}" style="--i:{index}">'
        f'<div class="lx-src-margin"><span class="lx-src-num" title="Cita [{p.number}]">{p.number}</span>{margin}</div>'
        '<div class="lx-src-body">'
        '<div class="lx-src-meta">'
        f'<span class="lx-file">{icon("draft")}{filename}</span>'
        + (f'<span class="lx-page">{icon("bookmark")}{page}</span>' if page else "")
        + f'<span class="lx-rel" title="Similitud con la pregunta">'
        f'<span class="lx-meter" style="--v:{meter * 100:.0f}%"><i></i></span>relevancia {_decimal(p.relevance)}</span>'
        "</div>"
        f'<details class="lx-text"><summary><span class="lx-excerpt"><span class="lx-hl">{esc(p.text)}</span></span>'
        '<span class="lx-more"></span></summary></details>'
        f"{boe}"
        "</div>"
        f"{stamp}"
        "</article>"
    )


def sources_section(
    passages: Iterable[Passage],
    marks: dict[int, str],
    link_for: Callable[[Passage], str | None],
    animate: bool = True,
) -> str:
    """``marks``: passage number → "cited" or "match". ``animate=False`` when re-drawing an
    answer the user has already seen (e.g. after switching the theme)."""
    passages = list(passages)
    ordered = sorted(passages, key=lambda p: (p.number not in marks, p.number))
    cards = "".join(source_card(p, marks.get(p.number), link_for(p), i) for i, p in enumerate(ordered))
    if "cited" in marks.values():
        note = ""
    elif marks:
        note = (
            f'<p class="lx-note">{icon("info")}El modelo no ha marcado la cita; se destaca el fragmento '
            "cuyo texto coincide con la respuesta.</p>"
        )
    else:
        note = f'<p class="lx-note">{icon("info")}El modelo no ha marcado qué fragmento usó; están ordenados por relevancia.</p>'

    return (
        f'<section class="lx-sources{"" if animate else " lx-static"}">'
        f'<div class="lx-h" role="heading" aria-level="2">{icon("menu_book")}Fuentes<span class="lx-count">{len(passages)}</span></div>'
        f"{note}{cards}"
        "</section>"
    )
