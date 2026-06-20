"""
Unit tests for the NFR Specialist node.

Tests cover:
- nfr_specialist_node returns nfr_content in state (LLM call mocked)
- nfr_content contains all five required section headings
- CAI gate assertion_2_nfr_structural passes/fails correctly
"""

from unittest.mock import MagicMock, patch

import pytest

from norma.graph.cai_gate import _NFR_REQUIRED_SECTIONS, _assertion_2_nfr_structural
from norma.graph.nfr_specialist import nfr_specialist_node

_VALID_NFR = "\n".join(
    [
        "## Tech Stack",
        "Python 3.12, FastAPI, Docker [assumed]",
        "",
        "## External APIs",
        "ZenQuotes API (https://zenquotes.io/api/random), JokeAPI (https://v2.jokeapi.dev/joke/Any). "
        "Fallback: return cached last response. [assumed]",
        "",
        "## Timeouts & Retries",
        "Per-call timeout: 5s. Max retries: 3. Back-off: exponential, 1s base. [assumed]",
        "",
        "## Auth Model",
        "None required for public API endpoints. [assumed]",
        "",
        "## Error Handling",
        "JSON error body {error: str}, HTTP 502 on upstream failure. Log at ERROR level. "
        "User-facing: 'Sorry, something went wrong. Please try again.'",
    ]
)

_BASE_STATE = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "A conversational app that greets the user by time of day.",
    "actors": ["user"],
    "external_deps": [],
    "gherkin_content": "Feature: Greeting\n  Scenario: Morning\n    Given it is 8am\n    When user opens app\n    Then they see 'Good Morning'",
}


# ── _assertion_2_nfr_structural ────────────────────────────────────────────────

def test_nfr_structural_passes_with_all_sections():
    ok, msg = _assertion_2_nfr_structural(_VALID_NFR)
    assert ok is True
    assert msg == ""


def test_nfr_structural_fails_missing_section():
    nfr_missing_auth = _VALID_NFR.replace("## Auth Model\n", "").replace(
        "None required for public API endpoints. [assumed]\n", ""
    )
    ok, msg = _assertion_2_nfr_structural(nfr_missing_auth)
    assert ok is False
    assert "## Auth Model" in msg


def test_nfr_structural_fails_empty_string():
    ok, msg = _assertion_2_nfr_structural("")
    assert ok is False
    for section in _NFR_REQUIRED_SECTIONS:
        assert section in msg


# ── nfr_specialist_node ────────────────────────────────────────────────────────

def _make_llm_response(content: str):
    return MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(
            return_value={
                "choices": [{"message": {"content": content}}]
            }
        ),
    )


@patch("norma.graph.nfr_specialist.Langfuse")
@patch("norma.graph.nfr_specialist.httpx.Client")
def test_nfr_specialist_node_returns_nfr_content(mock_client_cls, mock_langfuse_cls):
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value = mock_span
    mock_langfuse_cls.return_value = mock_lf

    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.post.return_value = _make_llm_response(_VALID_NFR)
    mock_client_cls.return_value = mock_http

    result = nfr_specialist_node(_BASE_STATE)

    assert "nfr_content" in result
    assert result["nfr_content"] == _VALID_NFR
    # Original state keys preserved
    assert result["raw_requirement"] == _BASE_STATE["raw_requirement"]


@patch("norma.graph.nfr_specialist.Langfuse")
@patch("norma.graph.nfr_specialist.httpx.Client")
def test_nfr_specialist_strips_markdown_fences(mock_client_cls, mock_langfuse_cls):
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)

    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value = mock_span
    mock_langfuse_cls.return_value = mock_lf

    fenced = f"```markdown\n{_VALID_NFR}\n```"
    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.post.return_value = _make_llm_response(fenced)
    mock_client_cls.return_value = mock_http

    result = nfr_specialist_node(_BASE_STATE)

    assert not result["nfr_content"].startswith("```")
    assert "## Tech Stack" in result["nfr_content"]
