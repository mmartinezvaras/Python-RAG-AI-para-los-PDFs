"""CI smoke test: open the Streamlit demo, ask an example question, check the
answer and its sources render, and save a screenshot (demo.png)."""

import re
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
QUESTION = "How many points does the winner of a Formula One race get?"

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
    page.get_by_text("Ask your PDFs").wait_for(timeout=120_000)
    page.get_by_role("button", name=QUESTION).click()
    page.get_by_role("heading", name="Sources").wait_for(timeout=300_000)
    page.locator("[data-testid='stExpander'] summary").first.click()  # expand first source
    time.sleep(2)
    answer = page.locator("[data-testid='stMarkdownContainer']").all_inner_texts()
    print("\n".join(answer))
    assert any(re.search(r"\b25\b|twenty-five", a, re.I) for a in answer), "Expected 25 in the answer"
    page.screenshot(path="demo.png", full_page=True)
    browser.close()

print("✅ Web demo works")
