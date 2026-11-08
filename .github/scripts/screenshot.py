"""CI smoke test: open the Streamlit demo, ask an example question, check the answer and its
sources render, then switch to the night theme. Saves demo.png (light) and demo-dark.png."""

import re
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
EXAMPLE_BUTTON = "Días de vacaciones"

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
    page = browser.new_page(viewport={"width": 1280, "height": 1500}, color_scheme="light", device_scale_factor=2)
    page.goto(URL)
    page.get_by_text("¿Qué dice el Estatuto de los Trabajadores?").wait_for(timeout=120_000)
    page.get_by_role("button", name=EXAMPLE_BUTTON).click()
    page.get_by_role("heading", name="Fuentes").wait_for(timeout=300_000)
    time.sleep(2)  # let the "Citado" stamp animation finish
    answer = page.locator(".lx-answer").inner_text()
    print(answer)
    assert re.search(r"\b30\b|treinta", answer, re.I), "Expected 30 days in the answer"
    assert page.locator(".lx-src").count() > 0, "Expected source cards"
    page.screenshot(path="demo.png", full_page=True)

    # Night theme: the stored answer is shown again without asking the model.
    page.get_by_text("Noche", exact=True).click()
    page.wait_for_function(
        "getComputedStyle(document.documentElement).getPropertyValue('--lx-paper').trim() === '#0E1524'",
        timeout=30_000,
    )
    page.get_by_role("heading", name="Fuentes").wait_for(timeout=60_000)
    time.sleep(2)
    page.screenshot(path="demo-dark.png", full_page=True)
    browser.close()

print("✅ Web demo works in light and night themes")
