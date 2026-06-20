"""
Unit tests for the intake node.

Tests cover:
- _parse_output extracts all three sections (inline format)
- _parse_output extracts sections in block format
- _parse_output strips bold markdown markers
- _parse_output handles missing ACTORS section gracefully
- _parse_output filters out 'none' deps
- intake_node returns all three keys in state (LLM mocked)
- intake_node falls back to raw LLM text when NORMALISED section absent
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from norma.graph.intake import _parse_output, intake_node
from norma.graph.state import NormaState

# ── helpers ────────────────────────────────────────────────────────────────────

_RAW = "Build a greeting app that says hello"

_BASE_STATE: NormaState = {"raw_requirement": _RAW}

_LLM_INLINE = (
    "NORMALISED: Build a web app that greets users by time of day.\n"
    "ACTORS:\n- End User\n- Greeting API\n"
    "EXTERNAL_DEPS:\n- ZenQuotes API\n- JokeAPI"
)

_LLM_BLOCK = (
    "NORMALISED:\nBuild a web app that greets users by time of day.\n"
    "ACTORS:\n- End User\n"
    "EXTERNAL_DEPS:\nnone"
)

_LLM_BOLD = (
    "**NORMALISED:** Build a web app.\n"
    "**ACTORS:**\n- End User\n"
    "**EXTERNAL_DEPS:**\nnone"
)


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


# ── _parse_output ──────────────────────────────────────────────────────────────

def test_parse_output_inline_format():
    normalised, actors, deps = _parse_output(_LLM_INLINE)
    assert normalised == "Build a web app that greets users by time of day."
    assert "End User" in actors
    assert "Greeting API" in actors
    assert "ZenQuotes API" in deps
    assert "JokeAPI" in deps


def test_parse_output_block_format():
    normalised, actors, deps = _parse_output(_LLM_BLOCK)
    assert normalised == "Build a web app that greets users by time of day."
    assert "End User" in actors
    assert deps == []


def test_parse_output_strips_bold_markdown():
    normalised, actors, deps = _parse_output(_LLM_BOLD)
    assert normalised == "Build a web app."
    assert "End User" in actors


def test_parse_output_filters_none_deps():
    text = "NORMALISED: App.\nACTORS:\n- User\nEXTERNAL_DEPS:\nnone"
    _, _, deps = _parse_output(text)
    assert deps == []


def test_parse_output_missing_actors_returns_empty_list():
    text = "NORMALISED: App.\nEXTERNAL_DEPS:\nnone"
    _, actors, _ = _parse_output(text)
    assert actors == []


def test_parse_output_fallback_when_no_normalised_section():
    text = "The system shall greet users."
    normalised, _, _ = _parse_output(text)
    assert normalised == text.strip()


def test_parse_output_strips_actor_description_after_dash():
    text = (
        "NORMALISED: App.\nACTORS:\n- End User — the human\n- Quote API — external\n"
        "EXTERNAL_DEPS:\nnone"
    )
    _, actors, _ = _parse_output(text)
    assert actors == ["End User", "Quote API"]


# ── intake_node (LLM mocked) ───────────────────────────────────────────────────

@pytest.mark.llm
@patch("norma.graph.intake.Langfuse")
@patch("norma.graph.intake.httpx.Client")
def test_intake_node_returns_all_keys(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http(_LLM_INLINE)
    mock_langfuse_cls.return_value = _make_langfuse()

    result = intake_node(_BASE_STATE)

    assert "normalised_requirement" in result
    assert "actors" in result
    assert "external_deps" in result
    assert result["normalised_requirement"] != ""


@pytest.mark.llm
@patch("norma.graph.intake.Langfuse")
@patch("norma.graph.intake.httpx.Client")
def test_intake_node_parses_actors_and_deps(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _make_http(_LLM_INLINE)
    mock_langfuse_cls.return_value = _make_langfuse()

    result = intake_node(_BASE_STATE)

    assert isinstance(result["actors"], list)
    assert isinstance(result["external_deps"], list)
    assert len(result["actors"]) > 0
