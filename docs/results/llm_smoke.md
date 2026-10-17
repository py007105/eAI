# LLM provider smoke test

Run by `scripts/llm_smoke.py` on 2026-10-17 09:57:38 UTC; Python 3.14.7, Windows-11-10.0.26300-SP0. One request per provider with a fixed fake incident context; this checks connectivity, latency and JSON-schema validity only, not diagnosis quality.

- Gemini model: `gemini-3.8-flash`; Groq model: `llama-3.3-70b-versatile`

## gemini

```json
{
 "provider": "gemini",
 "tested": true,
 "ok": true,
 "schema_valid": true,
 "latency_s": 6.92,
 "likely_cause": "memory_leak",
 "runbook_id": "restart_service",
 "summary": "The inventory service is exhibiting rapid memory growth at 118 MB/min, currently consuming 71% of its limit with projected memory exhaustion in 38 to 61 seconds. Concurrently, elevated latency ratio is observed while the container remains operational without an OOM event yet. A memory leak is the probable root cause requiring service intervention.",
 "agrees_with_engine": true
}
```

## groq

```json
{
 "provider": "groq",
 "tested": false,
 "note": "GROQ_API_KEY not set"
}
```
