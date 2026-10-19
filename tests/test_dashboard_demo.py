"""Demo mode: hidden pick from supported faults and healthy changes only; unseen segment only in ask-first; no second start while a
run is in progress or restoring (no 409 on stage); phases from the evaluator's own fields; scenario never reaches the page before the
reveal; one plain-language line per revealed run."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dashboard"))
import demo  # noqa: E402
import views  # noqa: E402
from labels import t  # noqa: E402


class Resp:
    def __init__(self, code, body):
        self.status_code, self._b = code, body

    def json(self):
        return self._b


class FakeEvaluator:
    """Records every request; answers like the evaluator's existing API."""
    def __init__(self):
        self.posts, self.state, self.runs, self.reveal_body, self.post_code = [], "running", 5, None, 200

    def post(self, url, json=None, timeout=None):
        self.posts.append(json)
        return Resp(self.post_code, {"run_id": f"r{len(self.posts)}"} if self.post_code == 200 else {"detail": "a run is already in progress"})

    def get(self, url, timeout=None):
        if url.endswith("/scorecard"):
            return Resp(200, {"runs": self.runs})
        if url.endswith("/status"):
            return Resp(200, {"state": self.state, "elapsed_s": 12.0})
        return Resp(200, self.reveal_body)


def test_pool_matches_the_terminal_helper_and_never_includes_the_unseen_fault():
    src = (ROOT / "scripts" / "demo_challenge.py").read_text(encoding="utf-8")
    pool = re.findall(r'"([a-z_]+)"', re.search(r"POOL = \[(.*?)\]", src).group(1))
    assert pool == demo.POOL and demo.UNSEEN == re.search(r'UNSEEN = "([a-z_]+)"', src).group(1)
    assert demo.UNSEEN not in demo.POOL


def test_hidden_start_sends_a_scenario_from_the_pool_only():
    seen = set()
    for _ in range(200):
        ev = FakeEvaluator()
        d = demo.DemoRuns("http://ev", ev)
        assert d.start("hidden", "ask-first") == (True, "demo_started")
        seen.add(ev.posts[0]["scenario"])
    assert seen <= set(demo.POOL) and "cpu_burn" not in seen and len(seen) > 4


def test_unseen_segment_only_in_ask_first():
    ev = FakeEvaluator()
    d = demo.DemoRuns("http://ev", ev)
    assert d.start("unseen", "autopilot") == (False, "demo_unseen_needs_ask_first") and not ev.posts
    assert d.start("unseen", "ask-first")[0] and ev.posts[-1] == {"scenario": "cpu_burn"}


def test_no_second_start_while_running_or_restoring_so_no_409():
    ev = FakeEvaluator()
    d = demo.DemoRuns("http://ev", ev)
    d.start("hidden", "ask-first")
    assert d.start("hidden", "ask-first") == (False, "demo_busy") and len(ev.posts) == 1
    ev.runs = 6                                   # scored, evaluator still "running": restoring
    d.poll()
    assert d.current()["phase"] == "restoring" and d.start("hidden", "ask-first") == (False, "demo_busy")
    ev.state = "finished"
    d.poll()
    assert d.current()["phase"] == "finished" and d.start("hidden", "ask-first")[0] and len(ev.posts) == 2


def test_a_run_started_elsewhere_gives_a_friendly_conflict_message():
    ev = FakeEvaluator()
    ev.post_code = 409
    assert demo.DemoRuns("http://ev", ev).start("hidden", "ask-first") == (False, "demo_conflict")


def test_reveal_only_after_the_evaluator_says_finished():
    ev = FakeEvaluator()
    d = demo.DemoRuns("http://ev", ev)
    d.start("hidden", "ask-first")
    assert d.reveal() == (False, "demo_not_finished")
    ev.state, ev.reveal_body = "finished", {"truth": {"scenario": "crash", "target": "orders"}, "score": {"detected": True, "recovered": True,
                                                                                                         "time_to_verified_recovery_s": 41.6, "failed_request_pct": 10.81}}
    d.poll()
    assert d.reveal() == (True, "demo_revealed")


def test_scenario_never_reaches_the_page_before_the_reveal():
    ev = FakeEvaluator()
    d = demo.DemoRuns("http://ev", ev)
    d.start("hidden", "ask-first")
    sent = ev.posts[0]["scenario"]
    page = str(views.demo_state(d.current(), None)) + str(views.demo_runs(d.runs, demo.summary))
    assert sent not in page and sent.replace("_", " ") not in page and "scenario" not in d.current()


def test_one_line_summaries():
    s = lambda scen, tgt, **sc: demo.summary({"truth": {"scenario": scen, "target": tgt}, "score": sc})
    assert s("crash", "orders", detected=True, recovered=True, time_to_verified_recovery_s=41.6, failed_request_pct=10.81) == \
        "crash on orders: recovered in 41.6 s (EternalAI's own checkout); 10.81% failed requests."
    assert s("disk_fill", "orders", detected=True, recovered=False, final_status="escalated", failed_request_pct=25.55) == \
        "disk fill on orders: not recovered (escalated); 25.55% failed requests."
    assert s("traffic_surge", "web", incidents_opened=0, failed_request_pct=0.0) == "traffic surge on web: healthy change, no incident; 0.0% failed requests."
    assert s("cpu_burn", "payments", abstained_correctly=True, failed_request_pct=0.0) == \
        "cpu burn on payments: unseen fault, abstained with no action; 0.0% failed requests."
    assert "\n" not in s("latency", "web", detected=False, failed_request_pct=3.0)


def test_indicator_phases_and_text():
    assert t("demo_idle_pill") in str(views.demo_state(None, None))
    run = {"run_id": "r1", "segment": "hidden", "phase": "restoring", "elapsed_s": 80.0, "reveal": None}
    assert "restoring the stack" in str(views.demo_state(run, None))
    assert "evaluator not answering" in str(views.demo_state(dict(run, phase="running"), "ConnectTimeout"))


def test_layout_has_demo_buttons_and_no_all_nine_scenarios_button():
    import app as dash_app
    s = str(dash_app.layout())
    for i in ("demo_hidden", "demo_unseen", "demo_reveal", "demo_state", "pending_ids", "alert_sink"):
        assert i in s
    assert "id='start'" not in s and "id='reveal'" not in s
    assert "/challenge/start" not in (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")


def test_evaluator_url_inside_compose_and_locally(monkeypatch):
    monkeypatch.delenv("EVALUATOR_URL", raising=False)
    monkeypatch.setenv("BACKEND_URL", "http://eternalai:8000")
    assert demo.evaluator_url() == "http://evaluator:8200"
    monkeypatch.setenv("BACKEND_URL", "http://localhost:8000")
    assert demo.evaluator_url() == "http://localhost:8200"


def test_new_proposal_alert_fires_once_per_proposal_and_does_not_wipe_itself():
    src = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    js = src[src.index("window._eaiSeen"):src.index('Output("alert_sink"')]
    assert "AudioContext" in js and "classList.add('flash')" in js
    assert "return window.dash_clientside.no_update" in js          # an unchanged poll must not clear the "alerted" marker
    assert "body.flash" in (ROOT / "dashboard" / "assets" / "style.css").read_text(encoding="utf-8")
