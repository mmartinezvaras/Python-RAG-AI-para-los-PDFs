"""What every page of the demo starts with: the theme CSS and the Auto / Claro / Noche switch.

Streamlit forgets a widget's value when you go to a page where that widget isn't drawn yet, so the
choice is also kept in ``st.session_state.tema`` (a plain value, which survives page changes) and
the switch is drawn from it on every page.
"""

import streamlit as st

from ui.theme import page_css

THEMES = {"auto": ("brightness_auto", "Auto"), "light": ("light_mode", "Claro"), "dark": ("dark_mode", "Noche")}


def _remember_theme():
    st.session_state.tema = st.session_state.theme


def theme_css_and_switch():
    """Inject the CSS of the chosen theme, then draw the switch. Returns the mode in use."""
    # The switch can be cleared (None): fall back to following the system setting.
    mode = st.session_state.get("tema") or "auto"
    # st.html, not st.markdown: CSS is full of "*" (selectors, calc, comments), which Markdown
    # would turn into emphasis and break the stylesheet.
    st.html(page_css(mode))
    if "theme" not in st.session_state:  # first visit, or coming from the other page
        st.session_state.theme = st.session_state.get("tema", "auto")
    st.segmented_control(
        "Tema",
        options=list(THEMES),
        format_func=lambda k: f":material/{THEMES[k][0]}: {THEMES[k][1]}",
        key="theme",
        on_change=_remember_theme,
        label_visibility="collapsed",
    )
    return mode
