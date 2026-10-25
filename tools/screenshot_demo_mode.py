"""Browser check and screenshots of Demo mode against fixture data (hand-made, not telemetry). Token field stays empty.

    python tools/screenshot_demo_mode.py

Starts tools/fixture_backend.py (brain and evaluator endpoints, FIXTURE=awaiting) and a dashboard on local ports, then: checks the
new-proposal alert fired (flash class and alert text), clicks "Start hidden challenge", records the indicator through running ->
restoring -> finished, clicks Reveal and reads the one-line summary. Saves docs/screenshots/demo_*.png.
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from screenshot_ui_states import start  # noqa: E402

OUT = ROOT / "docs" / "screenshots"


def main():
    procs = []
    try:
        procs.append(start(["tools/fixture_backend.py"], {"FIXTURE": "awaiting", "FIXTURE_PORT": "8120", "FIXTURE_RUN_S": "8"}, 8120, "/status"))
        procs.append(start(["dashboard/app.py"], {"PORT": "8070", "BACKEND_URL": "http://127.0.0.1:8120", "EVALUATOR_URL": "http://127.0.0.1:8120"}, 8070))
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": 1500, "height": 1250})
            pg.goto("http://127.0.0.1:8070", wait_until="load", timeout=60000)
            pg.wait_for_selector("#demo_state", timeout=60000)
            pg.wait_for_timeout(3000)
            print("alert:", pg.locator("#alert_sink").text_content(), "| title:", pg.title())
            demo_panel = pg.locator("#t_demo").locator("xpath=..")
            demo_panel.screenshot(path=OUT / "demo_1_ready.png")
            pg.fill("#token", "fixture-only-token")   # starting a run needs a token; the fixture evaluator ignores it
            pg.click("#demo_hidden")
            pg.wait_for_timeout(1500)
            pg.fill("#token", "")                     # cleared again before any further screenshot
            print("after start:", pg.locator("#demo_msg").inner_text(), "| hidden button disabled:", pg.locator("#demo_hidden").is_disabled())
            seen, t0 = [], time.time()
            while time.time() - t0 < 25:
                txt = pg.locator("#demo_indicator").inner_text().split("\n")[0]
                if not seen or seen[-1] != txt:
                    seen.append(txt)
                    if "progress" in txt:
                        demo_panel.screenshot(path=OUT / "demo_2_running.png")
                    if "restoring" in txt:
                        demo_panel.screenshot(path=OUT / "demo_3_restoring.png")
                if "finished" in txt:
                    break
                pg.wait_for_timeout(500)
            print("indicator sequence:", seen)
            pg.click("#demo_reveal")
            pg.wait_for_timeout(2500)
            print("summary:", pg.locator("#demo_runs").inner_text().replace("\n", " "))
            assert not pg.locator("#token").input_value(), "token field must be empty"
            demo_panel.screenshot(path=OUT / "demo_4_revealed.png")
            pg.screenshot(path=OUT / "demo_full.png", full_page=True)
            b.close()
    finally:
        for p in procs:
            p.kill()


if __name__ == "__main__":
    main()
