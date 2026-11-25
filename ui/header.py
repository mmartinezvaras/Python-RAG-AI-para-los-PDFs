"""What every page of the demo starts with: the theme CSS and the Auto / Claro / Noche switch.

The switch runs in the browser, not in Python: a click sets the ``data-lx-theme`` attribute of the
page, and the CSS (``ui/theme.py``) already holds both palettes, so the colours change at once,
with no round trip to the server. The choice is kept in the browser (localStorage), so it stays
when you move between pages or come back another day.
"""

import streamlit as st
import streamlit.components.v1 as components

from ui.theme import DARK, LIGHT, page_css

STORAGE_KEY = "tema-estatuto"

_ICONS = {
    "auto": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="8"/>'
    '<path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" stroke="none"/></svg>',
    "light": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    "dark": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
}
THEMES = {"auto": "Auto", "light": "Claro", "dark": "Noche"}


def switch_html() -> str:
    """The switch as a tiny page. It paints itself with the same palette as the demo."""
    buttons = "".join(
        f'<button type="button" role="radio" data-t="{key}" aria-checked="false">{_ICONS[key]}{label}</button>'
        for key, label in THEMES.items()
    )
    look = {
        "light": (LIGHT["sheet"], LIGHT["ring"], LIGHT["ink-2"], LIGHT["seal"], LIGHT["sheet"], LIGHT["seal-soft"]),
        "dark": (DARK["sheet"], DARK["ring"], DARK["ink-2"], DARK["seal"], DARK["sheet"], DARK["seal-soft"]),
    }
    css = "".join(
        f'body[data-look="{name}"] .sw {{ background: {bg}; box-shadow: 0 0 0 1px {ring}; }}'
        f'body[data-look="{name}"] button {{ color: {ink}; }}'
        f'body[data-look="{name}"] button[aria-checked="true"] {{ background: {on}; color: {on_text}; }}'
        f'@media (hover: hover) {{ body[data-look="{name}"] button:not([aria-checked="true"]):hover {{ background: {hover}; }} }}'
        for name, (bg, ring, ink, on, on_text, hover) in look.items()
    )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; background: transparent; color-scheme: normal; }}
body {{ display: flex; justify-content: flex-end; padding: 2px; font: 500 13.5px "Public Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.sw {{ display: inline-flex; gap: 2px; padding: 3px; border-radius: 999px; }}
button {{ border: 0; background: transparent; padding: 6px 12px; border-radius: 999px; cursor: pointer; font: inherit;
  display: inline-flex; align-items: center; gap: 6px; white-space: nowrap;
  transition: background-color 150ms cubic-bezier(.23,1,.32,1), color 150ms cubic-bezier(.23,1,.32,1), transform 160ms cubic-bezier(.23,1,.32,1); }}
button:active {{ transform: scale(.97); }}
button:focus-visible {{ outline: 2px solid currentColor; outline-offset: 2px; }}
svg {{ width: 15px; height: 15px; flex: none; }}
@media (max-width: 360px) {{ button {{ padding: 6px 9px; font-size: 12.5px; }} }}
{css}
</style></head><body data-look="light">
<div class="sw" role="radiogroup" aria-label="Tema">{buttons}</div>
<script>
  const page = window.parent.document.documentElement;
  const system = window.parent.matchMedia("(prefers-color-scheme: dark)");
  let current = "auto";
  try {{ current = window.parent.localStorage.getItem("{STORAGE_KEY}") || "auto"; }} catch (e) {{}}
  function apply(theme) {{
    current = theme;
    if (theme === "auto") delete page.dataset.lxTheme; else page.dataset.lxTheme = theme;
    document.body.dataset.look = theme === "auto" ? (system.matches ? "dark" : "light") : theme;
    document.querySelectorAll("button").forEach(b => b.setAttribute("aria-checked", String(b.dataset.t === theme)));
  }}
  apply(current);
  document.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {{
    apply(b.dataset.t);
    try {{ window.parent.localStorage.setItem("{STORAGE_KEY}", b.dataset.t); }} catch (e) {{}}
  }}));
  system.addEventListener("change", () => apply(current));  // auto follows the system live
</script></body></html>"""


def theme_css_and_switch() -> None:
    """Inject the CSS (both palettes), then draw the switch at the top right."""
    # st.html, not st.markdown: CSS is full of "*" (selectors, calc, comments), which Markdown
    # would turn into emphasis and break the stylesheet.
    st.html(page_css())
    with st.container(key="theme"):
        components.html(switch_html(), height=44)
