"""LLM incident report: Gemini first, Groq second, deterministic template last.

The model only returns JSON that validates against `IncidentReport`. It never writes commands.
The backend then checks: evidence_ids must exist, runbook_id must be one of the candidates the
deterministic table allows for the diagnosed cause, and the engine's own cause stays authoritative
(a disagreement is recorded, not obeyed). Keys come from the environment; with none, the template
report is used and everything still works.
"""
from __future__ import annotations

import json
import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from .classify import ABSTAIN, CLASSES

# Pinned, not a "-latest" alias, so results are reproducible. "gemini-2.5-flash" returned HTTP 404
# ("no longer available to new users") when tested on 2026-10-17; override with GEMINI_MODEL.
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"

CAUSES = tuple(c for c in CLASSES if c != "healthy") + (ABSTAIN,)
RUNBOOKS = ("restart_service", "recreate_container", "rollback_release", "clear_temp_path")
Cause = Literal[CAUSES]  # type: ignore[valid-type]
Runbook = Literal[RUNBOOKS]  # type: ignore[valid-type]


class IncidentReport(BaseModel):
    summary: str = Field(max_length=700)
    evidence_ids: list[str]
    likely_cause: Cause
    alternative_causes: list[Cause] = []
    runbook_id: Runbook | None = None
    missing_information: list[str] = []


SYSTEM = ("You are an SRE assistant. Using ONLY the evidence items provided, return a JSON object with keys: "
          "summary (string, 2-3 sentences), evidence_ids (list of the evidence ids you relied on), "
          f"likely_cause (exactly one of: {', '.join(CAUSES)}), "
          "alternative_causes (list; every item must be one of those same values, never free text), "
          "runbook_id (one of the candidate runbooks given in the input, or null), "
          "missing_information (a LIST of short strings, empty if nothing is missing). "
          "If evidence is insufficient use likely_cause 'insufficient_evidence' and runbook_id null. "
          "Never output shell commands.")

# Structured-output schema for Gemini (OpenAPI subset): the model is constrained to our enums, and the
# strict pydantic validation below still runs on whatever comes back.
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "evidence_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
        "likely_cause": {"type": "STRING", "enum": list(CAUSES)},
        "alternative_causes": {"type": "ARRAY", "items": {"type": "STRING", "enum": list(CAUSES)}},
        "runbook_id": {"type": "STRING", "enum": list(RUNBOOKS), "nullable": True},
        "missing_information": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "evidence_ids", "likely_cause", "alternative_causes", "missing_information"],
}


def template_report(ctx: dict) -> IncidentReport:
    cause = ctx["cause"]
    ev = [e["id"] for e in ctx["evidence"]][:6]
    top = ctx["ranking"][0]["service"] if ctx["ranking"] else "unknown"
    if cause == ABSTAIN:
        return IncidentReport(
            summary=f"Anomaly on {top} does not match a known fault pattern with enough confidence, so no "
                    f"automatic action is proposed. Evidence is preserved for a human.",
            evidence_ids=ev, likely_cause=ABSTAIN, runbook_id=None,
            missing_information=["fault pattern not seen in training", "human review needed"])
    rb = ctx["candidates"][0] if ctx["candidates"] else None
    return IncidentReport(
        summary=f"{top} shows signs of {cause.replace('_', ' ')} (classifier confidence "
                f"{ctx['confidence']:.2f}). Proposed runbook: {rb}. Recovery is only confirmed after the "
                f"synthetic checkout passes.",
        evidence_ids=ev, likely_cause=cause,
        alternative_causes=[c for c in ctx.get("alternatives", []) if c != cause][:2], runbook_id=rb)


def _prompt(ctx: dict) -> str:
    return json.dumps({"service_ranking": ctx["ranking"], "engine_diagnosis": ctx["cause"],
                       "candidate_runbooks": ctx["candidates"],
                       "evidence": [{"id": e["id"], "tool": e["tool"], "summary": e["summary"]}
                                    for e in ctx["evidence"]]})


def _gemini(prompt: str, client: httpx.Client) -> str:
    model = os.getenv("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
    r = client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": os.environ["GEMINI_API_KEY"]}, timeout=20,
                    json={"systemInstruction": {"parts": [{"text": SYSTEM}]},
                          "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                          "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1,
                                               "responseSchema": GEMINI_SCHEMA}})
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str, client: httpx.Client) -> str:
    r = client.post("https://api.groq.com/openai/v1/chat/completions", timeout=20,
                    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                    json={"model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), "temperature": 0.1,
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def llm_enabled() -> bool:
    return any(os.getenv(k) for k in ("GEMINI_API_KEY", "GROQ_API_KEY"))


def validate(raw: str, ctx: dict) -> IncidentReport:
    """Parse and constrain model output; raises ValueError when it breaks any rule."""
    try:
        rep = IncidentReport.model_validate_json(raw)
    except ValidationError as e:
        raise ValueError(f"schema: {e.errors()[0]['msg']}") from e
    known = {e["id"] for e in ctx["evidence"]}
    if not set(rep.evidence_ids) <= known:
        raise ValueError("evidence_ids reference unknown evidence")
    if rep.runbook_id is not None and rep.runbook_id not in ctx["candidates"]:
        raise ValueError(f"runbook_id {rep.runbook_id} is not an allowed candidate")
    return rep


def make_report(ctx: dict, client: httpx.Client | None = None) -> tuple[IncidentReport, dict]:
    """Return (report, meta). meta says which provider answered and whether it disagreed with the engine."""
    client = client or httpx.Client()
    prompt = _prompt(ctx)
    attempts = []
    for name, key, fn in (("gemini", "GEMINI_API_KEY", _gemini), ("groq", "GROQ_API_KEY", _groq)):
        if not os.getenv(key):
            continue
        try:
            rep = validate(fn(prompt, client), ctx)
            disagree = rep.likely_cause != ctx["cause"]
            if disagree:  # the engine's cause stays authoritative; the report text is kept for the human
                rep = rep.model_copy(update={"likely_cause": ctx["cause"],
                                             "runbook_id": ctx["candidates"][0] if ctx["candidates"] else None})
            return rep, {"provider": name, "llm_disagreed": disagree}
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as e:
            attempts.append(f"{name}: {type(e).__name__}")
    return template_report(ctx), {"provider": "template", "llm_disagreed": False, "fallback_reasons": attempts}
