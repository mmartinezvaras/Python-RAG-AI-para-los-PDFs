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
    # The theme switch must be fully visible, without scrolling, on desktop and on a phone.
    check_switch = """() => {
        const group = document.querySelector('.st-key-theme [data-testid="stButtonGroup"]');
        const box = group.getBoundingClientRect();
        const scrollers = [group, ...group.querySelectorAll('div')].filter(d => d.scrollWidth > d.clientWidth + 1);
        const hidden = [...group.querySelectorAll('button')].filter(b => {
            const r = b.getBoundingClientRect();
            return r.left < box.left - 1 || r.right > box.right + 1 || r.right > window.innerWidth;
        }).map(b => b.innerText.trim());
        return {scrolls: scrollers.length, hidden};
    }"""
    for width in (1280, 390):
        page.set_viewport_size({"width": width, "height": 1500})
        time.sleep(1)
        result = page.evaluate(check_switch)
        print(f"theme switch at {width}px: {result}")
        assert result == {"scrolls": 0, "hidden": []}, f"Theme switch not fully visible at {width}px: {result}"
    page.set_viewport_size({"width": 1280, "height": 1500})

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
        "getComputedStyle(document.documentElement).getPropertyValue('--lx-paper').trim() === '#000000'",
        timeout=30_000,
    )
    page.get_by_role("heading", name="Fuentes").wait_for(timeout=60_000)
    time.sleep(2)
    page.screenshot(path="demo-dark.png", full_page=True)
    # Contrast check of the selected theme button (text vs background), printed for the log.
    print(page.evaluate("""() => [...document.querySelectorAll('[data-testid="stButtonGroup"] button')].map(b => {
        const t = b.querySelector('p') || b; const cs = getComputedStyle(t), bs = getComputedStyle(b);
        return `${b.getAttribute('data-testid')} "${b.innerText.trim()}": text ${cs.color} on ${bs.backgroundColor}`;
    }).join('\\n')"""))
    browser.close()

print("✅ Web demo works in light and night themes")
