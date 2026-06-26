"""
Unit tests for the Spec Advisor node.

Tests cover:
- _parse_advice parses valid JSON with full SpecRecommendation fields
- _parse_advice tolerates markdown fences
- _parse_advice drops entries missing required fields
- _parse_advice drops entries with unsafe artefact_key values
- _parse_advice returns empty list on corrupt JSON
- spec_advisor_node returns spec_advice in state (LLM mocked)
- _dispatch_specialists returns correct Send commands
- _dispatch_specialists falls back to cai_gate on empty advice
"""

import json
from unittest.mock import MagicMock, patch

from norma.graph.spec_advisor import _parse_advice, spec_advisor_node
from norma.graph.state import NormaState, SpecRecommendation

# ── fixtures ───────────────────────────────────────────────────────────────────

_VALID_ITEM = {
    "language": "RFC 2119",
    "artefact_key": "rfc2119",
    "rationale": "Requirement states a 2-second SLA and graceful failure handling.",
    "depends_on": [],
    "requirement_segments": (
        "The app must respond within 2 seconds. "
        "When external APIs are unavailable the app must display a friendly fallback message."
    ),
    "role": "You are a standards author writing RFC 2119 conformance clauses.",
    "insight": "Two MUST constraints: 2-second latency ceiling and mandatory fallback on API failure.",
    "statement": "Produce '# Constraints' with MUST/SHOULD/MAY bullets under ## sections.",
}

_VALID_ITEM_2 = {
    "language": "OpenAPI 3.1",
    "artefact_key": "openapi",
    "rationale": "Requirement defines a REST endpoint.",
    "depends_on": [],
    "requirement_segments": (
        "The app exposes a GET /greet endpoint that returns a time-of-day greeting "
        "and the user's content choice."
    ),
    "role": "You are an API designer writing an OpenAPI 3.1 contract.",
    "insight": "One GET endpoint; response includes greeting string and content payload.",
    "statement": "Produce a valid openapi.yaml with paths, schemas, and error responses.",
}

_BASE_STATE: NormaState = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "An app greeting users by time of day with content choices.",
    "actors": ["user"],
    "external_deps": [],
}


# ── _parse_advice ──────────────────────────────────────────────────────────────

_WRAPPER = {"specialists": [_VALID_ITEM]}


def test_parse_advice_valid_full_recommendation():
    advice = _parse_advice(json.dumps(_WRAPPER))
    assert len(advice) == 1
    r = advice[0]
    assert r["language"] == "RFC 2119"
    assert r["artefact_key"] == "rfc2119"
    assert r["requirement_segments"] == _VALID_ITEM["requirement_segments"]
    assert r["role"] == _VALID_ITEM["role"]
    assert r["insight"] == _VALID_ITEM["insight"]
    assert r["statement"] == _VALID_ITEM["statement"]
    assert r["depends_on"] == []


def test_parse_advice_multiple_items():
    wrapper = {"specialists": [_VALID_ITEM, _VALID_ITEM_2]}
    advice = _parse_advice(json.dumps(wrapper))
    assert len(advice) == 2
    assert advice[1]["artefact_key"] == "openapi"


def test_parse_advice_strips_markdown_fences():
    text = "```json\n" + json.dumps(_WRAPPER) + "\n```"
    advice = _parse_advice(text)
    assert len(advice) == 1


def test_parse_advice_legacy_bare_array():
    """Bare array still parses correctly."""
    advice = _parse_advice(json.dumps([_VALID_ITEM]))
    assert len(advice) == 1


def test_parse_advice_drops_entry_missing_role():
    item = {**_VALID_ITEM, "role": ""}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice == []


def test_parse_advice_drops_entry_missing_requirement_segments():
    item = {k: v for k, v in _VALID_ITEM.items() if k != "requirement_segments"}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice == []


def test_parse_advice_drops_entry_missing_insight():
    item = {k: v for k, v in _VALID_ITEM.items() if k != "insight"}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice == []


def test_parse_advice_drops_unsafe_artefact_key():
    item = {**_VALID_ITEM, "artefact_key": "../../etc/passwd"}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice == []


def test_parse_advice_drops_artefact_key_with_spaces():
    item = {**_VALID_ITEM, "artefact_key": "open api"}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice == []


def test_parse_advice_returns_empty_on_corrupt_json():
    advice = _parse_advice("not json at all")
    assert advice == []


def test_parse_advice_normalises_artefact_key_to_lowercase():
    item = {**_VALID_ITEM, "artefact_key": "RFC2119"}
    advice = _parse_advice(json.dumps({"specialists": [item]}))
    assert advice[0]["artefact_key"] == "rfc2119"


# ── spec_advisor_node ──────────────────────────────────────────────────────────

def _mock_llm_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _mock_http(content: str) -> MagicMock:
    http = MagicMock()
    http.__enter__ = MagicMock(return_value=http)
    http.__exit__ = MagicMock(return_value=False)
    http.post.return_value = _mock_llm_response(content)
    return http


def _mock_langfuse() -> MagicMock:
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    prompt_client = MagicMock()
    prompt_client.prompt = "SYSTEM PROMPT STUB"
    lf = MagicMock()
    lf.start_as_current_observation.return_value = span
    lf.get_prompt.return_value = prompt_client
    return lf


@patch("norma.graph.spec_advisor.Langfuse")
@patch("norma.graph.spec_advisor.httpx.Client")
def test_spec_advisor_node_returns_spec_advice(mock_client_cls, mock_langfuse_cls):
    wrapper = {"specialists": [_VALID_ITEM]}
    mock_client_cls.return_value = _mock_http(json.dumps(wrapper))
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_advisor_node(_BASE_STATE)

    assert "spec_advice" in result
    assert len(result["spec_advice"]) == 1
    assert result["spec_advice"][0]["artefact_key"] == "rfc2119"
    assert result["spec_advice"][0]["role"] == _VALID_ITEM["role"]


@patch("norma.graph.spec_advisor.Langfuse")
@patch("norma.graph.spec_advisor.httpx.Client")
def test_spec_advisor_node_returns_empty_on_bad_llm_output(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _mock_http("I cannot determine the spec languages.")
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_advisor_node(_BASE_STATE)

    assert result["spec_advice"] == []


# ── _dispatch_specialists ─────────────────────────────────────────────────────

def test_dispatch_sends_one_per_recommendation():
    from langgraph.types import Send

    from norma.graph import _dispatch_specialists

    rec = SpecRecommendation(
        language="RFC 2119", artefact_key="rfc2119", rationale="x",
        depends_on=[], requirement_segments="seg", role="r", insight="i", statement="s",
    )
    state: NormaState = {**_BASE_STATE, "spec_advice": [rec]}
    result = _dispatch_specialists(state)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Send)
    assert result[0].node == "spec_specialist"
    assert result[0].arg["current_recommendation"]["artefact_key"] == "rfc2119"


def test_dispatch_sends_multiple_in_parallel():
    from langgraph.types import Send

    from norma.graph import _dispatch_specialists

    recs = [
        SpecRecommendation(language="RFC 2119", artefact_key="rfc2119", rationale="x",
                           depends_on=[], requirement_segments="seg1",
                           role="r", insight="i", statement="s"),
        SpecRecommendation(language="OpenAPI 3.1", artefact_key="openapi", rationale="y",
                           depends_on=[], requirement_segments="seg2",
                           role="r2", insight="i2", statement="s2"),
    ]
    state: NormaState = {**_BASE_STATE, "spec_advice": recs}
    result = _dispatch_specialists(state)

    assert len(result) == 2
    keys = {s.arg["current_recommendation"]["artefact_key"] for s in result}
    assert keys == {"rfc2119", "openapi"}


def test_dispatch_returns_cai_gate_on_empty_advice():
    from norma.graph import _dispatch_specialists

    state: NormaState = {**_BASE_STATE, "spec_advice": []}
    assert _dispatch_specialists(state) == "cai_gate"


def test_dispatch_returns_cai_gate_when_advice_absent():
    from norma.graph import _dispatch_specialists

    assert _dispatch_specialists(_BASE_STATE) == "cai_gate"
