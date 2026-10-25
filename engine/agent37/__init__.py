"""Agent37 integration: an LLM investigator hosted on Agent37 that explains EternalAI incidents.

The deterministic engine stays authoritative. Agent37 only reads a bounded incident brief and the results of local
read-only tools, and returns a structured finding. Its suggested runbook is checked by EternalAI's own PolicyEngine;
it can never execute, approve or change policy. If Agent37 is not configured, out of credit or failing, EternalAI runs
exactly as before.
"""
from .client import Agent37Client, Agent37Error  # noqa: F401
from .investigator import Investigator  # noqa: F401
