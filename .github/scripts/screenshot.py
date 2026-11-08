"""CI smoke test: open the Streamlit demo, ask an example question, check the
answer and its sources render, and save a screenshot (demo.png)."""

import re
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
QUESTION = "¿Cuántos días de vacaciones al año me corresponden?"

for _ in range(120):
    try:
        urllib.request.urlopen(URL, timeout=2)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Streamlit did not start")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(URL)
    page.get_by_text("Pregunta a tus PDFs").wait_for(timeout=120_000)
    page.get_by_role("button", name=QUESTION).click()
    page.get_by_role("heading", name="Fuentes").wait_for(timeout=300_000)
    time.sleep(3)  # let the streamed answer finish rendering
    answer = page.locator("[data-testid='stMarkdownContainer']").all_inner_texts()
    print("\n".join(answer))
    assert any(re.search(r"\b30\b|treinta", a, re.I) for a in answer), "Expected 30 days in the answer"
    page.screenshot(path="demo.png", full_page=True)
    browser.close()

print("✅ Web demo works")
