"""List Gemini models that support generateContent for the configured key. Prints names only, never the key."""
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import config  # noqa: E402,F401  (loads .env)

key = os.getenv("GEMINI_API_KEY")
if not key:
    sys.exit("GEMINI_API_KEY not set")
try:
    r = httpx.get("https://generativelanguage.googleapis.com/v1beta/models", params={"pageSize": 200}, headers={"x-goog-api-key": key}, timeout=20)
except httpx.HTTPError as e:
    sys.exit(f"request failed: {type(e).__name__}")
print("HTTP", r.status_code)
if r.status_code != 200:
    try:
        err = r.json().get("error", {})
        print("error status:", err.get("status"), "| message:", str(err.get("message", ""))[:200].replace(key, "[key]"))
    except ValueError:
        print("non-JSON error body")
    sys.exit(1)
names = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
print(len(names), "models support generateContent:")
print("\n".join(sorted(names)))
