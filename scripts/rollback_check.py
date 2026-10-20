"""Live check: evaluator deploys a bad release; the executor rolls it back; checkout recovers.

    python scripts/rollback_check.py [service]
"""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eternalai.collector import DockerView  # noqa: E402
from eternalai.executor import Executor  # noqa: E402
from eternalai.verify import verify_recovery  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness_auth import check_started, evaluator_headers  # noqa: E402

svc = sys.argv[1] if len(sys.argv) > 1 else "orders"
EV = "http://localhost:8200"
dv, ex = DockerView(), Executor()
rid = check_started(httpx.post(f"{EV}/runs", headers=evaluator_headers(), json={"scenario": "bad_deploy", "target": svc, "timeout_s": 60}, timeout=20)).json()["run_id"]
print("evaluator started a run (scenario hidden from us)")
# wait until the bad release is observable: image tag changes to a higher release sequence
for _ in range(120):
    st = dv.poll()[svc]
    if st.release_seq >= 3:
        break
    time.sleep(2)
print("observed:", svc, "tag", st.image_tag, "release_seq", st.release_seq)
print("checkout while bad:", verify_recovery(6))
print("rollback:", ex.run("rollback_release", svc, "rollback_check"))
time.sleep(4)
print("observed after rollback:", dv.poll()[svc].image_tag)
print("checkout after rollback:", verify_recovery(10))
while httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"] == "running":
    time.sleep(5)
print("run finished:", httpx.get(f"{EV}/runs/{rid}/status", timeout=10).json()["state"])
