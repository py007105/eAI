"""Thin client for the Agent37 HTTP API (https://www.agent37.com/docs).

Verified from the official docs (llms-full.txt, 25 Oct 2026):
- A turn runs on the instance: POST https://{instance_id}.agent37.app/v1/responses, header X-Agent37-Key.
  Body: input (required), session_id, model, metadata. Response: id, session_id, status
  (completed | failed | cancelled), output_text, usage {input_tokens, output_tokens, cost_usd}, error.
  A failed turn returns HTTP 200 with status "failed".
- Control plane: https://api.agent37.com, header Authorization: Bearer. GET /v1/instances/{id}/budget
  (monthly_cap_micros, monthly_consumed_micros, monthly_remaining_micros), GET /v1/instances/{id}/usage,
  POST /v1/instances/{id}/stop.
- 402 reasons: insufficient_balance (wallet empty), instance_budget_exhausted (per-instance cap hit, provider-enforced).
- 503 wake_timeout when a sleeping instance does not wake within the gateway's budget; 413 payload_too_large (2 MB).
The key is read from the environment only and never logged or returned.
"""
from __future__ import annotations

import os

import httpx

CONTROL_URL = "https://api.agent37.com"


class Agent37Error(Exception):
    """code: not_configured | insufficient_credit | budget_exhausted | wake_timeout | timeout | http_<n> | turn_failed |
    network | payload_too_large"""

    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


def _detail(r: httpx.Response) -> str:
    try:
        body = r.json()
    except ValueError:
        return r.text[:200]
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("code") or err.get("message") or "")[:200]
    return str(err or body.get("detail") or "")[:200] if isinstance(body, dict) else ""


class Agent37Client:
    def __init__(self, api_key: str | None = None, instance_id: str | None = None, instance_url: str | None = None,
                 timeout_s: float | None = None, transport: httpx.BaseTransport | None = None):
        self._key = api_key if api_key is not None else os.getenv("AGENT37_API_KEY", "")
        self.instance_id = instance_id if instance_id is not None else os.getenv("AGENT37_INSTANCE_ID", "")
        self.instance_url = (instance_url or os.getenv("AGENT37_INSTANCE_URL", "")
                             or (f"https://{self.instance_id}.agent37.app" if self.instance_id else "")).rstrip("/")
        self.model = os.getenv("AGENT37_MODEL") or None          # None: the instance's default (low-cost) model
        self.timeout_s = timeout_s or float(os.getenv("AGENT37_TIMEOUT_S", "180"))
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self._key and self.instance_url)

    def _http(self, timeout: float) -> httpx.Client:
        return httpx.Client(timeout=timeout, transport=self._transport)

    def respond(self, text: str, session_id: str | None = None, metadata: dict | None = None) -> dict:
        """One agent turn. Returns the response object; raises Agent37Error on any failure."""
        if not self.configured:
            raise Agent37Error("not_configured", "set AGENT37_API_KEY and AGENT37_INSTANCE_ID")
        body: dict = {"input": text, "stream": False}
        if session_id:
            body["session_id"] = session_id
        if self.model:
            body["model"] = self.model
        if metadata:
            body["metadata"] = {k: str(v)[:200] for k, v in list(metadata.items())[:16]}
        try:
            with self._http(self.timeout_s) as c:
                r = c.post(f"{self.instance_url}/v1/responses", json=body,
                           headers={"X-Agent37-Key": self._key, "Content-Type": "application/json"})
        except httpx.TimeoutException:
            raise Agent37Error("timeout", f"no answer within {self.timeout_s:.0f} s")
        except httpx.HTTPError as e:
            raise Agent37Error("network", type(e).__name__)
        if r.status_code == 402:
            d = _detail(r)
            raise Agent37Error("budget_exhausted" if "budget" in d else "insufficient_credit", d)
        if r.status_code == 503 and "wake" in _detail(r):
            raise Agent37Error("wake_timeout", "instance did not wake in time; retry in a minute")
        if r.status_code == 413:
            raise Agent37Error("payload_too_large", "brief over 2 MB")
        if r.status_code >= 400:
            raise Agent37Error(f"http_{r.status_code}", _detail(r))
        out = r.json()
        if out.get("status") != "completed":
            err = out.get("error") or {}
            code = str(err.get("code") or out.get("status") or "turn_failed")
            if "budget" in code:
                raise Agent37Error("budget_exhausted", code)
            if "balance" in code:
                raise Agent37Error("insufficient_credit", code)
            raise Agent37Error("turn_failed", f"{code}: {str(err.get('message') or '')[:200]}")
        return out

    def _control(self, method: str, path: str) -> dict:
        if not (self._key and self.instance_id):
            raise Agent37Error("not_configured", "set AGENT37_API_KEY and AGENT37_INSTANCE_ID")
        try:
            with self._http(20) as c:
                r = c.request(method, f"{CONTROL_URL}{path}", headers={"Authorization": f"Bearer {self._key}"})
        except httpx.HTTPError as e:
            raise Agent37Error("network", type(e).__name__)
        if r.status_code >= 400:
            raise Agent37Error(f"http_{r.status_code}", _detail(r))
        return r.json()

    def budget(self) -> dict:
        """Provider-enforced per-instance cap (free to read)."""
        return self._control("GET", f"/v1/instances/{self.instance_id}/budget")

    def usage(self) -> dict:
        return self._control("GET", f"/v1/instances/{self.instance_id}/usage")

    def stop(self) -> dict:
        """Stop the instance (bills disk only while stopped)."""
        return self._control("POST", f"/v1/instances/{self.instance_id}/stop")
