"""Debug one Gemini call with the real EternalAI prompt; prints the raw JSON (the key is never printed)."""
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eternalai import config  # noqa: E402,F401  (loads .env)
from eternalai import llm  # noqa: E402
from llm_smoke import CTX  # noqa: E402

key = os.getenv("GEMINI_API_KEY")
try:
    raw = llm._gemini(llm._prompt(CTX), httpx.Client())
except httpx.HTTPStatusError as e:
    sys.exit(f"HTTP {e.response.status_code}")
print(json.dumps(json.loads(raw), indent=1, ensure_ascii=False)[:2500])
try:
    llm.validate(raw, CTX)
    print("VALID")
except ValueError as e:
    print("INVALID:", e)
