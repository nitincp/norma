"""
Unit tests for the Gherkin Specialist node.

Tests cover:
- gherkin_specialist_node returns gherkin_content in state (LLM mocked)
- Output starts with 'Feature:' keyword
- Markdown fences are stripped from LLM output (if present)
- Fixture-based: load state_post_intake.json, assert output shape
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from norma.graph.gherkin_specialist import gherkin_specialist_node
from norma.graph.state import NormaState

FIXTURES = Path(__file__).parent / "fixtures"

_VALID_FEATURE = (
    "Feature: Greeting App\n"
    "  Scenario: Morning greeting\n"
    "    Given it is 8am\n"
    "    When the user opens the app\n"
    "    Then they see 'Good Morning'\n"
)

_FEATURE_WITH_FENCES = f"```gherkin\n{_VALID_FEATURE}```"


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


# ── unit tests ─────────────────────────────────────────────────────────────────

@pytest.mark.llm
@patch("norma.graph.gherkin_specialist.Langfuse")
@patch("norma.graph.gherkin_specialist.httpx.Client")
def test_gherkin_specialist_returns_content_key(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http(_VALID_FEATURE)
    mock_langfuse_cls.return_value = _make_langfuse()

    state: NormaState = {
        "raw_requirement": "Build a greeting app",
        "normalised_requirement": "An app that greets users by time of day.",
        "actors": ["End User"],
        "external_deps": [],
    }
    result = gherkin_specialist_node(state)

    assert "gherkin_content" in result
    assert result["gherkin_content"].strip() != ""


@pytest.mark.llm
@patch("norma.graph.gherkin_specialist.Langfuse")
@patch("norma.graph.gherkin_specialist.httpx.Client")
def test_gherkin_specialist_output_starts_with_feature(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http(_VALID_FEATURE)
    mock_langfuse_cls.return_value = _make_langfuse()

    state: NormaState = {
        "raw_requirement": "Build a greeting app",
        "normalised_requirement": "An app that greets users by time of day.",
        "actors": ["End User"],
        "external_deps": [],
    }
    result = gherkin_specialist_node(state)

    assert result["gherkin_content"].strip().startswith("Feature:")


@pytest.mark.llm
@patch("norma.graph.gherkin_specialist.Langfuse")
@patch("norma.graph.gherkin_specialist.httpx.Client")
def test_gherkin_specialist_strips_markdown_fences(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http(_FEATURE_WITH_FENCES)
    mock_langfuse_cls.return_value = _make_langfuse()

    state: NormaState = {
        "raw_requirement": "Build a greeting app",
        "normalised_requirement": "An app that greets users by time of day.",
        "actors": ["End User"],
        "external_deps": [],
    }
    result = gherkin_specialist_node(state)

    assert "```" not in result["gherkin_content"]
    assert result["gherkin_content"].strip().startswith("Feature:")


# ── fixture-based tests ────────────────────────────────────────────────────────

@pytest.mark.llm
@patch("norma.graph.gherkin_specialist.Langfuse")
@patch("norma.graph.gherkin_specialist.httpx.Client")
def test_gherkin_specialist_from_intake_fixture(mock_client_cls, mock_langfuse_cls):
    """Load real post-intake state from fixture; verify node output shape."""
    mock_client_cls.return_value = _make_http(_VALID_FEATURE)
    mock_langfuse_cls.return_value = _make_langfuse()

    state = json.loads((FIXTURES / "state_post_intake.json").read_text())

    result = gherkin_specialist_node(state)

    assert "gherkin_content" in result
    assert result["gherkin_content"].strip().startswith("Feature:")
