"""Second page of the web demo: how the project is built (steps, problems, technologies).

Opens at /como_esta_hecho. Linked from the demo's header and sidebar.
"""

import streamlit as st

from ui.header import theme_css_and_switch
from ui.project_page import PROJECT_CSS, project_html

st.set_page_config(page_title="Cómo está hecho · Asistente del Estatuto", page_icon=":material/construction:")
theme_css_and_switch()
st.page_link("app.py", label="Volver a la demo", icon=":material/arrow_back:")
st.html(PROJECT_CSS)  # a stylesheet on its own, like the theme
st.html(project_html())
