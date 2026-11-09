"""Record a short video of the web demo for the README: type a question, watch the answer stream
in and the sources arrive with their stamp, then switch to the night theme.

Writes demo.webm and trim.txt (seconds to cut from the start: page load). The workflow turns
it into demo.gif with ffmpeg.
"""

import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
QUESTION = "¿Cuántos días de vacaciones al año me corresponden?"
SIZE = {"width": 1280, "height": 800}

for _ in range(180):
    try:
        urllib.request.urlopen(URL, timeout=2)
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Streamlit did not start")

out = Path("video")
with sync_playwright() as p:
    browser = p.chromium.launch()
    # Warm-up visit so the recording doesn't include the first-visit indexing or model start.
    warm = browser.new_page(viewport=SIZE)
    warm.goto(URL)
    warm.get_by_text("¿Qué dice el Estatuto de los Trabajadores?").wait_for(timeout=600_000)
    warm.locator('[data-testid="stTextInput"] input').wait_for(timeout=600_000)
    warm.close()

    context = browser.new_context(
        viewport=SIZE, record_video_dir=str(out), record_video_size=SIZE, color_scheme="light"
    )
    started = time.monotonic()
    page = context.new_page()
    page.goto(URL)
    field = page.locator('[data-testid="stTextInput"] input')
    field.wait_for(timeout=120_000)
    time.sleep(1.0)  # fonts and icons settle
    trim = time.monotonic() - started - 0.2

    field.click()
    page.keyboard.type(QUESTION, delay=45)
    time.sleep(0.4)
    page.keyboard.press("Enter")

    page.get_by_role("heading", name="Fuentes").wait_for(timeout=120_000)
    time.sleep(0.8)
    for _ in range(4):  # scroll so the source cards and the stamp come into view
        page.mouse.wheel(0, 170)
        time.sleep(0.12)
    time.sleep(2.2)

    for _ in range(4):
        page.mouse.wheel(0, -170)
        time.sleep(0.1)
    time.sleep(0.6)
    page.get_by_text("Noche", exact=True).click()
    time.sleep(1.4)
    for _ in range(3):
        page.mouse.wheel(0, 170)
        time.sleep(0.12)
    time.sleep(1.6)

    video = page.video.path()
    context.close()
    browser.close()

Path("demo.webm").write_bytes(Path(video).read_bytes())
Path("trim.txt").write_text(f"{max(trim, 0):.2f}")
print(f"✅ Recorded demo.webm (trim {trim:.1f} s)")
