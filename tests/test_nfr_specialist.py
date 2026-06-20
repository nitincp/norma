"""
Unit tests for the NFR Specialist node (REQ-002, now retired from the graph).

The nfr_specialist_node module is retained but no longer wired into the pipeline;
the Spec Advisor + RFC 2119 Specialist replace it from REQ-003 onward.

Tests cover:
- nfr_specialist_node returns nfr_content in state (LLM call mocked)
- Markdown fences are stripped from LLM output
"""

from unittest.mock import MagicMock, patch

from norma.graph.nfr_specialist import nfr_specialist_node

_VALID_NFR = "\n".join(
    [
        "## Tech Stack",
        "Python 3.12, FastAPI, Docker [assumed]",
        "",
        "## External APIs",
        "ZenQuotes API, JokeAPI. Fallback: cached response. [assumed]",
        "",
        "## Timeouts & Retries",
        "Per-call timeout: 5s. Max retries: 3. [assumed]",
        "",
        "## Auth Model",
        "None required for public API endpoints. [assumed]",
        "",
        "## Error Handling",
        "HTTP 502 on upstream failure. Log at ERROR level.",
    ]
)

_BASE_STATE = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "A conversational app that greets the user by time of day.",
    "actors": ["user"],
    "external_deps": [],
    "gherkin_content": (
        "Feature: Greeting\n  Scenario: Morning\n"
        "    Given it is 8am\n    When user opens app\n    Then they see 'Good Morning'"
    ),
}


def _make_llm_response(content: str):
    return MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={"choices": [{"message": {"content": content}}]}),
    )


def _mock_httpx(content: str):
    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.post.return_value = _make_llm_response(content)
    return mock_http


def _mock_langfuse():
    mock_span = MagicMock()
    mock_span.__enter__ = MagicMock(return_value=mock_span)
    mock_span.__exit__ = MagicMock(return_value=False)
    mock_lf = MagicMock()
    mock_lf.start_as_current_observation.return_value = mock_span
    return mock_lf


@patch("norma.graph.nfr_specialist.Langfuse")
@patch("norma.graph.nfr_specialist.httpx.Client")
def test_nfr_specialist_node_returns_nfr_content(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _mock_httpx(_VALID_NFR)
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = nfr_specialist_node(_BASE_STATE)

    assert result == {"nfr_content": _VALID_NFR}


@patch("norma.graph.nfr_specialist.Langfuse")
@patch("norma.graph.nfr_specialist.httpx.Client")
def test_nfr_specialist_strips_markdown_fences(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _mock_httpx(f"```markdown\n{_VALID_NFR}\n```")
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = nfr_specialist_node(_BASE_STATE)

    assert not result["nfr_content"].startswith("```")
    assert "## Tech Stack" in result["nfr_content"]
