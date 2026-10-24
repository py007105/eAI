"""Capture real browser screenshots of the standalone preview (must already be running on 127.0.0.1:8071).

    python dashboard/preview/capture_screenshots.py docs/screenshots

Headless Chromium via Playwright. Writes charts_empty.png (inventory, tick 0), charts_preview_en.png (inventory, tick 59,
English) and charts_preview_hi.png (the same in Hindi), and prints what each page showed (banner visible, labels, the
explanation text). Set PYTHONIOENCODING=utf-8 on a Windows console so the Hindi lines print.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def set_tick(page, value):
    h = page.locator("#tick [role=slider]").first
    h.focus()
    h.press("Home")
    if value:
        h.press("End")
    page.wait_for_function(f"document.querySelector('#tick-label') && document.querySelector('#tick-label').innerText.trim().endsWith(': {value}')", timeout=10000)
    page.wait_for_timeout(1200)


def set_lang(page, label):
    page.locator("#lang").click()
    page.get_by_role("option", name=label).click()
    page.wait_for_timeout(1500)


def report(page, name):
    print(name, "| banner:", page.locator("#synthetic-banner").is_visible(),
          "|", page.locator("#service-label").inner_text(), "|", page.locator("#tick-label").inner_text(),
          "| traces:", page.locator("#chart .scatterlayer .trace").count(),
          "| explanation:", page.locator("#explanation").inner_text().replace("\n", " / ")[:300])


with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1100, "height": 1000})
    page.goto("http://127.0.0.1:8071/")
    page.wait_for_selector("#chart .main-svg", timeout=20000)
    page.wait_for_timeout(1500)
    set_tick(page, 0)
    report(page, "charts_empty.png")
    page.screenshot(path=str(OUT / "charts_empty.png"), full_page=True)
    set_tick(page, 59)
    report(page, "charts_preview_en.png")
    page.screenshot(path=str(OUT / "charts_preview_en.png"), full_page=True)
    set_lang(page, "हिन्दी")
    report(page, "charts_preview_hi.png")
    page.screenshot(path=str(OUT / "charts_preview_hi.png"), full_page=True)
    b.close()
