"""The prompt, the Gemini response schema and the pydantic validator must describe the same allowed values.
Regression: the first live Gemini call returned free-text alternative_causes and a string missing_information."""
from typing import get_args

from engine import llm
from engine.llm import CAUSES, RUNBOOKS, GEMINI_SCHEMA, IncidentReport, SYSTEM


def test_schema_enums_match_validator_literals():
    props = IncidentReport.model_json_schema()["properties"]
    assert set(props["likely_cause"]["enum"]) == set(CAUSES) == set(GEMINI_SCHEMA["properties"]["likely_cause"]["enum"])
    assert set(GEMINI_SCHEMA["properties"]["alternative_causes"]["items"]["enum"]) == set(CAUSES)
    assert set(GEMINI_SCHEMA["properties"]["runbook_id"]["enum"]) == set(RUNBOOKS)
    assert set(get_args(llm.Runbook)) == set(RUNBOOKS)


def test_prompt_states_every_allowed_cause_and_list_fields():
    for c in CAUSES:
        assert c in SYSTEM
    assert "LIST" in SYSTEM and "never free text" in SYSTEM


def test_required_fields_exist_in_model():
    assert set(GEMINI_SCHEMA["required"]) <= set(IncidentReport.model_fields)
