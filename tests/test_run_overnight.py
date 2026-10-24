"""scripts/run_overnight.py: window times roll over midnight correctly, and a second runner is refused."""
import importlib.util
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ovn", ROOT / "scripts" / "run_overnight.py")
ovn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ovn)


def test_window_times():
    launched = datetime(2026, 10, 24, 13, 30, tzinfo=ovn.IST)
    start = ovn.at("21:00", launched)
    assert (start.day, start.hour) == (24, 21)
    assert (ovn.at("23:30", start).day, ovn.at("01:30", start).day, ovn.at("05:00", start).day) == (24, 25, 25)


def test_a_second_runner_is_refused(tmp_path):
    (tmp_path / "runner.pid").write_text(str(os.getpid()))      # this test process is alive
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_overnight.py"), "--log-dir", str(tmp_path),
                        "--candidate", "x", "--combined", "y", "--reference", "z"], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "another runner is alive" in r.stderr
