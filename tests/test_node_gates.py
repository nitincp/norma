"""
Unit tests for Stage 1 Gate and Stage 2 Gate nodes.

Strategy: test the non-LLM assertions directly (no mocking needed) and
mock the LLM-based assertion to verify PASS/FAIL verdict parsing and
the correct keys returned in state.

Stage 1 Gate tests:
- _assertion_1_env_plausibility passes with options present
- _assertion_1_env_plausibility fails when empty
- stage1_gate_node returns stage1_passed=True + gherkin_business on PASS (LLM mocked)
- stage1_gate_node returns stage1_passed=False + feedback on assertion 1 fail
- stage1_gate_node returns stage1_passed=False + feedback on LLM rubric fail (LLM mocked)

Stage 2 Gate tests:
- _assertion_1_gherkin_technical_structural passes on valid Gherkin
- _assertion_1_gherkin_technical_structural fails when Feature: missing
- _assertion_1_gherkin_technical_structural fails when no Scenario blocks
- _assertion_1_rfc2119_structural passes on valid RFC artefact
- _assertion_1_rfc2119_structural fails when # Constraints heading missing
- _assertion_1_rfc2119_structural fails when no MUST/SHOULD/MAY keywords
- stage2_gate_node returns gate_passed=True on PASS (LLM mocked)
- stage2_gate_node returns gate_passed=False + feedback on non-LLM fail
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from norma.graph.stage1_gate import (
    _assertion_1_env_plausibility,
    stage1_gate_node,
)
from norma.graph.stage2_gate import (
    _assertion_1_gherkin_technical_structural,
    _assertion_1_rfc2119_structural,
    stage2_gate_node,
)
from norma.graph.state import EnvironmentOption, NormaState

FIXTURES = Path(__file__).parent / "fixtures"

# ── shared fixtures ────────────────────────────────────────────────────────────

_ENV_OPTION: EnvironmentOption = {
    "runtime": "Python 3.12 + FastAPI",
    "framework": "FastAPI",
    "deployment": "Docker",
    "rationale": "Well-suited for REST APIs.",
    "rank": 1,
}

_VALID_GHERKIN = (
    "Feature: Greeting App\n"
    "  @technical\n"
    "  Scenario: API responds within 2 seconds\n"
    "    Given the app is running\n"
    "    When a user requests a greeting\n"
    "    Then the response arrives within 2 seconds\n"
)

_VALID_RFC = (
    "# Constraints\n\n"
    "## Performance\n"
    "- The system MUST respond within 2 seconds.\n"
    "- The system SHOULD cache API responses.\n"
)

_BASE_STAGE1_STATE: NormaState = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "An app that greets users by time of day.",
    "actors": ["End User"],
    "external_deps": [],
    "gherkin_content": _VALID_GHERKIN,
    "environment_options": [_ENV_OPTION],
}

_BASE_STAGE2_STATE: NormaState = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "An app that greets users by time of day.",
    "actors": ["End User"],
    "external_deps": [],
    "gherkin_business": _VALID_GHERKIN,
    "gherkin_technical": _VALID_GHERKIN,
    "spec_artefacts": {"rfc2119": _VALID_RFC},
    "selected_environment": _ENV_OPTION,
    "stage1_passed": True,
    "stage1_feedback": "",
}


def _make_llm_response(content: str) -> MagicMock:
    return MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={"choices": [{"message": {"content": content}}]}),
    )


def _make_http(content: str) -> MagicMock:
    http = MagicMock()
    http.__enter__ = MagicMock(return_value=http)
    http.__exit__ = MagicMock(return_value=False)
    http.post.return_value = _make_llm_response(content)
    return http


def _make_langfuse() -> MagicMock:
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    lf = MagicMock()
    lf.start_as_current_observation.return_value = span
    return lf


# ── Stage 1 Gate: non-LLM assertion ───────────────────────────────────────────

def test_stage1_assertion1_passes_with_options():
    state: NormaState = {**_BASE_STAGE1_STATE}
    ok, msg = _assertion_1_env_plausibility(state)
    assert ok is True
    assert msg == ""


def test_stage1_assertion1_fails_with_no_options():
    state: NormaState = {**_BASE_STAGE1_STATE, "environment_options": []}
    ok, msg = _assertion_1_env_plausibility(state)
    assert ok is False
    assert msg != ""


def test_stage1_assertion1_fails_when_key_absent():
    state: NormaState = {
        k: v for k, v in _BASE_STAGE1_STATE.items() if k != "environment_options"
    }
    ok, msg = _assertion_1_env_plausibility(state)
    assert ok is False


# ── Stage 1 Gate: node (LLM mocked) ───────────────────────────────────────────

@pytest.mark.llm
@patch("norma.graph.stage1_gate.Langfuse")
@patch("norma.graph.stage1_gate.httpx.Client")
def test_stage1_gate_pass_returns_gherkin_business(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http("PASS")
    mock_langfuse_cls.return_value = _make_langfuse()

    result = stage1_gate_node(_BASE_STAGE1_STATE)

    assert result["stage1_passed"] is True
    assert result["gherkin_business"] == _VALID_GHERKIN
    assert result["stage1_feedback"] == ""


@pytest.mark.llm
@patch("norma.graph.stage1_gate.Langfuse")
@patch("norma.graph.stage1_gate.httpx.Client")
def test_stage1_gate_fail_env_returns_false(mock_client_cls, mock_langfuse_cls):
    mock_langfuse_cls.return_value = _make_langfuse()
    state = {k: v for k, v in _BASE_STAGE1_STATE.items() if k != "environment_options"}

    result = stage1_gate_node(state)

    assert result["stage1_passed"] is False
    assert result["stage1_feedback"] != ""


@pytest.mark.llm
@patch("norma.graph.stage1_gate.Langfuse")
@patch("norma.graph.stage1_gate.httpx.Client")
def test_stage1_gate_fail_llm_rubric(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http("FAIL: Missing error path scenario.")
    mock_langfuse_cls.return_value = _make_langfuse()

    result = stage1_gate_node(_BASE_STAGE1_STATE)

    assert result["stage1_passed"] is False
    assert "FAIL" in result["stage1_feedback"]


# ── Stage 2 Gate: non-LLM assertions ──────────────────────────────────────────

def test_stage2_gherkin_structural_passes_valid():
    ok, msg = _assertion_1_gherkin_technical_structural(_VALID_GHERKIN)
    assert ok is True


def test_stage2_gherkin_structural_fails_no_feature():
    bad = _VALID_GHERKIN.replace("Feature:", "Functionality:")
    ok, msg = _assertion_1_gherkin_technical_structural(bad)
    assert ok is False
    assert "Feature:" in msg


def test_stage2_gherkin_structural_fails_no_scenario():
    bad = "Feature: Greeting App\n  Given a user\n  Then they see hello\n"
    ok, msg = _assertion_1_gherkin_technical_structural(bad)
    assert ok is False


def test_stage2_gherkin_structural_fails_no_steps():
    bad = "Feature: Greeting App\n  Scenario: empty\n"
    ok, msg = _assertion_1_gherkin_technical_structural(bad)
    assert ok is False


def test_stage2_rfc2119_structural_passes_valid():
    ok, msg = _assertion_1_rfc2119_structural(_VALID_RFC)
    assert ok is True


def test_stage2_rfc2119_structural_fails_no_constraints_heading():
    bad = _VALID_RFC.replace("# Constraints", "# Requirements")
    ok, msg = _assertion_1_rfc2119_structural(bad)
    assert ok is False
    assert "Constraints" in msg


def test_stage2_rfc2119_structural_fails_no_keywords():
    bad = "# Constraints\n\nThe system shall respond quickly."
    ok, msg = _assertion_1_rfc2119_structural(bad)
    assert ok is False


# ── Stage 2 Gate: node (LLM mocked) ───────────────────────────────────────────

@pytest.mark.llm
@patch("norma.graph.stage2_gate.Langfuse")
@patch("norma.graph.stage2_gate.httpx.Client")
def test_stage2_gate_pass_sets_gate_passed(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http("PASS")
    mock_langfuse_cls.return_value = _make_langfuse()

    result = stage2_gate_node(_BASE_STAGE2_STATE)

    assert result["gate_passed"] is True
    assert result["gate_feedback"] == ""


@pytest.mark.llm
@patch("norma.graph.stage2_gate.Langfuse")
@patch("norma.graph.stage2_gate.httpx.Client")
def test_stage2_gate_fail_on_bad_gherkin(mock_client_cls, mock_langfuse_cls):
    mock_langfuse_cls.return_value = _make_langfuse()
    state = {
        **_BASE_STAGE2_STATE,
        "gherkin_technical": "This is not valid Gherkin.",
    }

    result = stage2_gate_node(state)

    assert result["gate_passed"] is False
    assert result["gate_feedback"] != ""


@pytest.mark.llm
@patch("norma.graph.stage2_gate.Langfuse")
@patch("norma.graph.stage2_gate.httpx.Client")
def test_stage2_gate_fail_llm_rubric(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http("FAIL: Missing error path coverage.")
    mock_langfuse_cls.return_value = _make_langfuse()

    result = stage2_gate_node(_BASE_STAGE2_STATE)

    assert result["gate_passed"] is False
    assert "FAIL" in result["gate_feedback"]


# ── fixture-based smoke ────────────────────────────────────────────────────────

def test_stage2_rfc2119_structural_on_fixture():
    """Non-LLM structural check on the real spec_artefacts from a saved run."""
    state = json.loads((FIXTURES / "state_post_specialists.json").read_text())
    rfc = state.get("spec_artefacts", {}).get("rfc2119", "")
    if not rfc:
        pytest.skip("rfc2119 artefact not present in fixture")
    ok, msg = _assertion_1_rfc2119_structural(rfc)
    assert ok is True, f"Real RFC artefact failed structural check: {msg}"
