"""Smoke-test each configured LLM provider once: real latency and schema validity.

    python tools/llm_smoke.py [--out docs/results/llm_smoke.md]

Keys are read from the environment / .env and are NEVER printed or written. Exceptions are reduced to
their class and HTTP status, because an httpx error message can contain the request URL (which carries
the Gemini key as a query parameter). Providers without a key are reported as "not tested".
"""
import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import config  # noqa: E402,F401  (loads .env)
from engine import llm  # noqa: E402

CTX = {"cause": "memory_leak", "confidence": 0.93, "candidates": ["recreate_container", "restart_service"],
       "alternatives": ["bad_deploy"], "ranking": [{"service": "inventory", "score": 0.74}, {"service": "orders", "score": 0.19}],
       "evidence": [
           {"id": "ev1", "tool": "metrics", "summary": "inventory window metrics: lat_ratio=4.2, error_ratio=0.38, mem_share=0.71"},
           {"id": "ev2", "tool": "forecast", "summary": "inventory memory rising 118.0 MB/min, 71% of limit; exhaustion in 38-61s"},
           {"id": "ev3", "tool": "container", "summary": "inventory container running, image tag v1, exit_code=0, oom_killed=False"}]}


def probe(name, fn, key_env):
    if not os.getenv(key_env):
        return {"provider": name, "tested": False, "note": f"{key_env} not set"}
    t0 = time.perf_counter()
    try:
        raw = fn(llm._prompt(CTX), httpx.Client())
        latency = time.perf_counter() - t0
    except httpx.HTTPStatusError as e:
        msg = ""
        try:  # the server's own message (it does not contain the key); redact defensively anyway
            msg = str(e.response.json().get("error", {}).get("message", ""))[:200].replace(os.environ[key_env], "[key]")
        except (ValueError, AttributeError):
            pass
        return {"provider": name, "tested": True, "ok": False, "latency_s": round(time.perf_counter() - t0, 2),
                "error": f"HTTP {e.response.status_code}", "server_message": msg}
    except Exception as e:  # class name only: the message may embed the URL and key
        return {"provider": name, "tested": True, "ok": False, "latency_s": round(time.perf_counter() - t0, 2),
                "error": type(e).__name__}
    try:
        rep = llm.validate(raw, CTX)
        return {"provider": name, "tested": True, "ok": True, "schema_valid": True, "latency_s": round(latency, 2),
                "likely_cause": rep.likely_cause, "runbook_id": rep.runbook_id, "summary": rep.summary,
                "agrees_with_engine": rep.likely_cause == CTX["cause"]}
    except ValueError as e:
        return {"provider": name, "tested": True, "ok": True, "schema_valid": False, "latency_s": round(latency, 2),
                "validation_error": str(e)[:160], "raw_head": raw[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/results/llm_smoke.md")
    a = ap.parse_args()
    results = [probe("gemini", llm._gemini, "GEMINI_API_KEY"), probe("groq", llm._groq, "GROQ_API_KEY")]
    lines = ["# LLM provider smoke test\n",
             f"Run by `tools/llm_smoke.py` on {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}; "
             f"Python {platform.python_version()}, {platform.platform()}. One request per provider with a fixed fake "
             f"incident context; this checks connectivity, latency and JSON-schema validity only, not diagnosis quality.\n",
             f"- Gemini model: `{os.getenv('GEMINI_MODEL', llm.GEMINI_DEFAULT_MODEL)}`; Groq model: "
             f"`{os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}`\n"]
    for r in results:
        lines.append(f"## {r['provider']}\n")
        lines.append("```json\n" + json.dumps(r, indent=1, ensure_ascii=False) + "\n```\n")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
