"""Theme for the demo, built on Marcos's "Apple Style" palette (skill: paleta-colores-marcos):

    Negro Elegancia #000000 · Apagado Grafito #555555 · Apagado Plata #86868B
    Suave Índigo #F5F5F7 · Blanco Pureza #FFFFFF

Monochrome on purpose: in light mode black ink is the accent (citations, stamp, focus), in night
mode white is. Serif for the text of the law. Applied over Streamlit's own widgets with CSS
custom properties.

``page_css(mode)`` with mode "light", "dark" or "auto" (follows the operating system).
"""

# The five palette colours. Anything else below is derived from them (alpha or a mix).
NEGRO, GRAFITO, PLATA, INDIGO, BLANCO = "#000000", "#555555", "#86868B", "#F5F5F7", "#FFFFFF"

LIGHT = {
    "paper": INDIGO,  # page
    "sheet": BLANCO,  # cards, sidebar
    "field": BLANCO,
    "ink": NEGRO,  # main text (21:1)
    "ink-2": GRAFITO,  # secondary text (7.5:1 on white). Plata is only 3.6:1: never small text here
    "rule": "rgba(134, 134, 139, 0.35)",  # Plata, translucent
    "seal": NEGRO,  # accent: citations, stamp, focus
    "seal-soft": INDIGO,
    "mark": "rgba(134, 134, 139, 0.28)",  # Plata highlighter on the cited source
    "shadow": "rgba(0, 0, 0, 0.06)",
    "ring": "rgba(0, 0, 0, 0.08)",  # hairline around cards (semi-transparent, not a solid border)
    "lift": "0 1px 2px rgba(0, 0, 0, 0.04), 0 4px 16px -6px rgba(0, 0, 0, 0.10)",
    "skel": INDIGO,
    "halo": "rgba(0, 0, 0, 0.12)",  # focus ring and "jump to source" flash
}

DARK = {
    "paper": NEGRO,
    "sheet": "#141414",  # Negro + 24% Grafito
    "field": "#1C1C1C",  # Negro + 33% Grafito
    "ink": INDIGO,  # 16.9:1 on cards
    "ink-2": PLATA,  # 5.1:1 on cards
    "rule": "rgba(134, 134, 139, 0.30)",
    "seal": BLANCO,
    "seal-soft": "rgba(255, 255, 255, 0.10)",
    "mark": "rgba(134, 134, 139, 0.35)",
    "shadow": "rgba(0, 0, 0, 0.5)",
    "ring": "rgba(255, 255, 255, 0.10)",
    "lift": "0 1px 2px rgba(0, 0, 0, 0.5), 0 6px 20px -8px rgba(0, 0, 0, 0.8)",
    "skel": "#1C1C1C",
    "halo": "rgba(255, 255, 255, 0.20)",
}

FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Public+Sans:wght@400;500;600;700"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;0,8..60,700;1,8..60,400"
    "&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0"
    "&display=swap"
)


def _vars(tokens: dict[str, str]) -> str:
    return "".join(f"--lx-{k}:{v};" for k, v in tokens.items())


def _scheme_rules(mode: str) -> str:
    light = f":root{{{_vars(LIGHT)}color-scheme:light;}}"
    dark = f":root{{{_vars(DARK)}color-scheme:dark;}}"
    if mode == "dark":
        return dark
    if mode == "auto":
        return light + f"@media (prefers-color-scheme: dark){{{dark}}}"
    return light


BASE_CSS = """
:root {
  --lx-ease-out: cubic-bezier(0.23, 1, 0.32, 1);       /* strong ease-out for UI */
  --lx-ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
}
html { -webkit-tap-highlight-color: transparent; }
/* ---------- Page and Streamlit surfaces ---------- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: var(--lx-paper);
  color: var(--lx-ink);
  font-family: "Public Sans", system-ui, sans-serif;
  transition: background-color 250ms ease, color 250ms ease;
}
[data-testid="stHeader"] { background: transparent; }
.stApp p, .stApp li, .stApp label, .stApp a, .stApp button, .stApp input, .stApp small,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] {
  font-family: "Public Sans", system-ui, sans-serif;
}
[data-testid="stSidebar"] {
  background: var(--lx-sheet);
  border-right: 1px solid var(--lx-rule);
}
.stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] { color: var(--lx-ink); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--lx-ink-2); }
.stApp a { color: var(--lx-seal); }
.stApp hr { border-color: var(--lx-rule); }
[data-testid="stSidebar"] h3 { font-size: 1rem; font-weight: 600; }

/* Text input. Streamlit wraps the field in several containers with their own background and
   border: the outer one gets ours, everything inside is made clear. */
[data-testid="stTextInputRootElement"] {
  background: var(--lx-field) !important;
  border: 1.5px solid var(--lx-rule) !important;
  border-radius: 14px !important;
  box-shadow: 0 1px 2px var(--lx-shadow);
  transition: border-color 150ms ease, box-shadow 150ms ease;
}
[data-testid="stTextInputRootElement"] * { background-color: transparent !important; border-color: transparent !important; }
[data-testid="stTextInputRootElement"]:focus-within {
  border-color: var(--lx-seal) !important;
  box-shadow: 0 0 0 4px var(--lx-halo);
}
[data-testid="stTextInput"] [data-baseweb="base-input"], [data-testid="stTextInput"] input {
  background: transparent; color: var(--lx-ink); font-size: 1.05rem;
}
[data-testid="stTextInput"] input { padding: .85rem 1rem; }
[data-testid="stTextInput"] input::placeholder { color: var(--lx-ink-2); opacity: .8; }

/* Buttons: example questions, theme switch */
.stButton button, [data-testid="stButtonGroup"] button {
  background: var(--lx-sheet);
  color: var(--lx-ink);
  border: 1px solid var(--lx-rule);
  border-radius: 999px;
  font-weight: 500;
  transition: border-color 150ms ease, background-color 150ms ease, transform 160ms var(--lx-ease-out);
}
@media (hover: hover) and (pointer: fine) {
  .stButton button:hover, [data-testid="stButtonGroup"] button:hover {
    border-color: var(--lx-seal); color: var(--lx-ink); background: var(--lx-seal-soft);
  }
}
.stButton button:active, [data-testid="stButtonGroup"] button:active { transform: scale(.97); }
.stButton button:focus-visible, [data-testid="stButtonGroup"] button:focus-visible {
  outline: 2px solid var(--lx-seal); outline-offset: 2px;
}
.stButton button [data-testid="stIconMaterial"], [data-testid="stButtonGroup"] [data-testid="stIconMaterial"] {
  color: var(--lx-seal);
}
/* Selected theme. Streamlit paints it with primaryColor (black), invisible on the night background. */
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stBaseButton-segmented_controlActive"] {
  background: var(--lx-seal) !important; border-color: var(--lx-seal) !important;
}
[data-testid="stButtonGroup"] button[kind*="Active"] *, [data-testid="stBaseButton-segmented_controlActive"] *,
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stBaseButton-segmented_controlActive"] {
  color: var(--lx-sheet) !important;
}

/* Sidebar widgets */
[data-testid="stExpander"] details {
  background: var(--lx-paper); border: 1px solid var(--lx-rule); border-radius: 12px;
}
[data-testid="stExpander"] summary, [data-testid="stExpander"] summary p { color: var(--lx-ink); }
[data-testid="stFileUploaderDropzone"] {
  background: var(--lx-paper); border: 1.5px dashed var(--lx-rule); border-radius: 12px; color: var(--lx-ink-2);
}
[data-testid="stFileUploaderDropzone"] button { background: var(--lx-sheet); color: var(--lx-ink); border-color: var(--lx-rule); }
[data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stFileUploaderDropzoneInstructions"] small {
  color: var(--lx-ink-2);
}

/* ---------- Our components ---------- */
.ms {
  font-family: "Material Symbols Rounded"; font-weight: 400; font-style: normal;
  font-size: 1.2em; line-height: 1; vertical-align: -0.22em; margin-right: .4em;
  font-variation-settings: "FILL" 0, "opsz" 24; user-select: none;
}
.lx-hero h1 {
  font-family: "Source Serif 4", Georgia, serif; font-weight: 600;
  font-size: clamp(1.9rem, 4.2vw, 2.6rem); line-height: 1.12; letter-spacing: -0.02em;
  margin: 0 0 .5rem; padding: 0; color: var(--lx-ink);
}
.lx-hero { margin-bottom: 1.4rem; }
.lx-hero p { color: var(--lx-ink-2); font-size: 1.02rem; line-height: 1.55; max-width: 62ch; margin: 0; }
.lx-hero p strong { color: var(--lx-ink); font-weight: 600; }

.lx-h {
  font-family: "Public Sans", system-ui, sans-serif; font-size: .95rem; font-weight: 600;
  color: var(--lx-ink-2); margin: 0 0 .75rem; padding: 0; display: flex; align-items: center;
}
.lx-h .ms { color: var(--lx-seal); }
.lx-count {
  margin-left: .5rem; font-size: .78rem; font-weight: 600; color: var(--lx-seal);
  background: var(--lx-seal-soft); border-radius: 999px; padding: .1rem .5rem;
  font-variant-numeric: tabular-nums;
}
.lx-note { color: var(--lx-ink-2); font-size: .9rem; margin: .25rem 0 .75rem; line-height: 1.5; }

/* Answer */
.lx-answer {
  background: var(--lx-sheet); border-left: 4px solid var(--lx-seal);
  border-radius: 6px 16px 16px 6px; padding: 1.15rem 1.4rem 1.2rem;
  box-shadow: 0 0 0 1px var(--lx-ring), var(--lx-lift); margin: .5rem 0 1.75rem;
}
.lx-answer-body p {
  font-family: "Source Serif 4", Georgia, serif; font-size: 1.16rem; line-height: 1.65;
  color: var(--lx-ink); margin: 0 0 .6rem; max-width: 65ch;
}
.lx-answer-body p:last-child { margin-bottom: 0; }
.lx-cite {
  display: inline-flex; align-items: center; justify-content: center; min-width: 1.35em; height: 1.35em;
  margin: 0 .1em; padding: 0 .3em; border-radius: 999px; vertical-align: .35em;
  font-family: "Public Sans", sans-serif; font-size: .62em; font-weight: 700; text-decoration: none;
  color: var(--lx-seal) !important; background: var(--lx-seal-soft); border: 1px solid transparent;
  transition: border-color 150ms ease;
}
@media (hover: hover) and (pointer: fine) { .lx-cite:hover { border-color: var(--lx-seal); } }
.lx-caret {
  display: inline-block; width: .5em; height: 1.05em; margin-left: .1em; vertical-align: -0.15em;
  background: var(--lx-seal); border-radius: 2px; animation: lx-blink 1s steps(2, start) infinite;
}
.lx-notfound { border-left-color: var(--lx-ink-2); }
.lx-notfound .lx-h .ms { color: var(--lx-ink-2); }

/* Searching */
.lx-searching .lx-h { color: var(--lx-ink); }
.lx-spin { animation: lx-pulse 1.4s ease-in-out infinite; }
.lx-skel-wrap { display: grid; gap: .55rem; }
.lx-skel {
  display: block; height: .8rem; border-radius: 6px;
  background: linear-gradient(90deg, var(--lx-skel) 0%, var(--lx-mark) 45%, var(--lx-skel) 90%);
  background-size: 220% 100%; animation: lx-shimmer 1.3s linear infinite;
}
.lx-skel:nth-child(2) { width: 92%; } .lx-skel:nth-child(3) { width: 64%; }

/* Sources */
.lx-src {
  position: relative; display: grid; grid-template-columns: 4.6rem 1fr; gap: 1rem;
  background: var(--lx-sheet); border-radius: 14px; box-shadow: 0 0 0 1px var(--lx-ring), var(--lx-lift);
  padding: 1rem 1.1rem; margin-bottom: .75rem; scroll-margin-top: 5rem;
  /* Sources arrive together when the answer is ready: stagger them 50 ms apart */
  animation: lx-enter 300ms var(--lx-ease-out) both; animation-delay: calc(var(--i, 0) * 50ms);
}
.lx-src.is-cited { box-shadow: 0 0 0 1px color-mix(in srgb, var(--lx-seal) 45%, transparent), var(--lx-lift); }
.lx-src:target { animation: lx-flash 900ms var(--lx-ease-out); }
.lx-src-margin {
  display: flex; flex-direction: column; align-items: flex-start; gap: .4rem;
  border-right: 1px solid var(--lx-rule); padding-right: .6rem;
}
.lx-src-num {
  font-size: .72rem; font-weight: 700; color: var(--lx-ink-2); border: 1px solid var(--lx-rule);
  border-radius: 999px; min-width: 1.5rem; height: 1.5rem; display: inline-flex;
  align-items: center; justify-content: center;
}
.is-cited .lx-src-num { color: var(--lx-seal); border-color: var(--lx-seal); background: var(--lx-seal-soft); }
.lx-art {
  font-family: "Source Serif 4", Georgia, serif; font-weight: 700; font-size: 1.9rem; line-height: 1;
  color: var(--lx-ink); display: flex; flex-direction: column; letter-spacing: -0.02em;
}
.lx-art-pre { font-family: "Public Sans", sans-serif; font-size: .72rem; font-weight: 600; color: var(--lx-ink-2); letter-spacing: 0; margin-bottom: .15rem; }
.is-cited .lx-art { color: var(--lx-seal); }
.lx-art-file .ms { font-size: 1.6rem; color: var(--lx-ink-2); margin: 0; }
.lx-src-body { min-width: 0; }
.lx-src-meta {
  display: flex; flex-wrap: wrap; align-items: center; gap: .35rem 1rem;
  font-size: .82rem; color: var(--lx-ink-2); margin-bottom: .5rem; padding-right: 5.5rem;
}
.lx-src-meta .ms { font-size: 1.05rem; margin-right: .25em; }
.lx-rel { display: inline-flex; align-items: center; gap: .45rem; font-variant-numeric: tabular-nums; }
.lx-meter { width: 3.6rem; height: .38rem; border-radius: 999px; background: var(--lx-skel); overflow: hidden; display: inline-block; }
.lx-meter i { display: block; height: 100%; width: var(--v); background: var(--lx-seal); border-radius: inherit; }
.lx-text summary { list-style: none; cursor: pointer; }
.lx-text summary::-webkit-details-marker { display: none; }
.lx-excerpt {
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
  font-family: "Source Serif 4", Georgia, serif; font-size: .98rem; line-height: 1.6; color: var(--lx-ink);
  white-space: pre-line;
}
.is-cited .lx-hl {
  background: linear-gradient(transparent 58%, var(--lx-mark) 58%);
  -webkit-box-decoration-break: clone; box-decoration-break: clone;
}
.lx-text[open] .lx-excerpt { -webkit-line-clamp: unset; display: block; }
.lx-more { display: inline-flex; align-items: center; margin-top: .35rem; font-size: .82rem; font-weight: 600; color: var(--lx-seal); }
.lx-more::before { content: "Leer el fragmento completo"; }
.lx-text[open] .lx-more::before { content: "Mostrar menos"; }
.lx-text summary:focus-visible { outline: 2px solid var(--lx-seal); outline-offset: 4px; border-radius: 6px; }
.lx-boe {
  display: inline-flex; align-items: center; margin-top: .6rem; font-size: .85rem; font-weight: 600;
  color: var(--lx-seal) !important; text-decoration: none !important; border-bottom: 1px solid transparent;
}
@media (hover: hover) and (pointer: fine) { .lx-boe:hover { border-bottom-color: var(--lx-seal); } }
.lx-boe .ms { font-size: 1.05rem; margin-right: .3em; }

/* The "Citado" stamp: the one orchestrated moment, when the answer is ready */
.lx-stamp {
  position: absolute; top: .75rem; right: .9rem; pointer-events: none;
  font-family: "Source Serif 4", Georgia, serif; font-weight: 700; font-size: .9rem; letter-spacing: .06em;
  color: var(--lx-seal); border: 2px solid var(--lx-seal); border-radius: 6px; padding: .12rem .55rem;
  box-shadow: inset 0 0 0 2px var(--lx-sheet), inset 0 0 0 3px var(--lx-seal);
  transform: rotate(-8deg); opacity: .88;
  /* Lands after its card has entered (card delay + 200 ms) */
  animation: lx-stamp 380ms var(--lx-ease-out) both; animation-delay: calc(var(--i, 0) * 50ms + 200ms);
}
.lx-stamp-match { border-style: dashed; box-shadow: none; opacity: .8; }
/* Re-drawing a stored answer (e.g. after switching the theme) is not news: no entrance motion */
.lx-static .lx-src, .lx-static .lx-stamp { animation: none; }

@keyframes lx-blink { to { visibility: hidden; } }
@keyframes lx-pulse { 50% { opacity: .45; } }
@keyframes lx-shimmer { from { background-position: 120% 0; } to { background-position: -120% 0; } }
@keyframes lx-enter { from { opacity: 0; transform: translateY(8px); } }
@keyframes lx-stamp {
  0% { opacity: 0; transform: scale(1.5) rotate(-14deg); }
  70% { opacity: .95; transform: scale(.97) rotate(-7.5deg); }
  100% { opacity: .88; transform: scale(1) rotate(-8deg); }
}
@keyframes lx-flash { 0%, 35% { box-shadow: 0 0 0 4px var(--lx-halo), 0 0 0 1px var(--lx-seal); } }
@keyframes lx-fade { from { opacity: 0; } }

/* Reduced motion: fewer and gentler, not zero. Keep fades, drop movement. */
@media (prefers-reduced-motion: reduce) {
  .lx-src { animation-name: lx-fade; }
  .lx-stamp { animation-name: lx-fade; }
  .lx-skel { animation: none; }
  .lx-caret { animation: none; }
  .stButton button:active, [data-testid="stButtonGroup"] button:active { transform: none; }
}
@media (max-width: 640px) {
  .lx-src { grid-template-columns: 1fr; gap: .6rem; }
  .lx-src-margin { flex-direction: row; align-items: center; border-right: 0; padding-right: 0; }
  .lx-art { flex-direction: row; align-items: baseline; gap: .3rem; font-size: 1.5rem; }
  .lx-src-meta { padding-right: 0; }
}
"""


def page_css(mode: str = "auto") -> str:
    return f'<style>@import url("{FONTS}");{_scheme_rules(mode)}{BASE_CSS}</style>'
