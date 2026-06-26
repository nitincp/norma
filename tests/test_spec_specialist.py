"""
Unit tests for the Spec Specialist shell node.

Tests cover:
- shell node produces artefact from current_recommendation CRISPE brief
- artefact stored under correct artefact_key in spec_artefacts
- existing spec_artefacts are preserved (fan-in accumulation)
- markdown fences stripped from LLM output
- _build_crispe assembles all six CRISPE fields correctly
- two-phase self-anchoring: ## EXAMPLE / ## ARTEFACT extraction
"""

from unittest.mock import MagicMock, patch

from norma.graph.spec_specialist import (
    _STATEMENT_PREFIX,
    _build_crispe,
    _parse_crispe_section,
    spec_specialist_node,
)
from norma.graph.state import NormaState, SpecRecommendation

_RFC2119_REC = SpecRecommendation(
    language="RFC 2119",
    artefact_key="rfc2119",
    rationale="Requirement states SLA and failure constraints.",
    depends_on=[],
    requirement_segments=(
        "The app must respond within 2 seconds. "
        "When external APIs are unavailable the app must display a friendly fallback message."
    ),
    role="You are a standards author writing RFC 2119 / RFC 8174 conformance clauses.",
    insight="Two MUST constraints: 2-second latency ceiling and mandatory fallback on API failure.",
    statement=(
        "Produce a document starting with '# Constraints'. "
        "Group MUST/SHOULD/MAY statements under ## themed sub-sections. "
        "One bullet per statement. Mark inferred constraints with [implied]."
    ),
)

_RFC2119_ARTEFACT = (
    "# Constraints\n\n"
    "## Performance\n"
    "- MUST respond within 2 seconds. [implied]\n\n"
    "## Availability\n"
    "- MUST NOT propagate upstream API errors to the user without a fallback message."
)

_RFC2119_EXAMPLE = (
    "# Constraints\n\n"
    "## <Theme>\n"
    "- MUST <verb> <object>.\n"
    "- SHOULD <verb> <object>.\n"
    "- MAY <verb> <object>."
)

_RFC2119_CONTENT = f"## EXAMPLE\n{_RFC2119_EXAMPLE}\n\n## ARTEFACT\n{_RFC2119_ARTEFACT}"

_BASE_STATE: NormaState = {
    "raw_requirement": "Build a greeting app",
    "normalised_requirement": "An app greeting users by time of day with content choices.",
    "actors": ["user"],
    "external_deps": [],
    "current_recommendation": _RFC2119_REC,
}


def _mock_http(content: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    http = MagicMock()
    http.__enter__ = MagicMock(return_value=http)
    http.__exit__ = MagicMock(return_value=False)
    http.post.return_value = resp
    return http


_STUB_CAPACITY = "Act as a senior specification author with deep expertise in the formal standard you have been briefed to apply."
_STUB_PERSONALITY = "Standards-conformant and precise. Use the exact terminology of the target standard."
_STUB_EXPERIMENT = "Follow the two-phase structure in STATEMENT exactly: output '## EXAMPLE' then '## ARTEFACT'. Mark inferred content with [implied] inline."

_STUB_PROMPT_TEXT = (
    f"CAPACITY:\n{_STUB_CAPACITY}\n\n"
    f"PERSONALITY:\n{_STUB_PERSONALITY}\n\n"
    f"EXPERIMENT:\n{_STUB_EXPERIMENT}"
)


def _mock_langfuse() -> MagicMock:
    span = MagicMock()
    span.__enter__ = MagicMock(return_value=span)
    span.__exit__ = MagicMock(return_value=False)
    prompt_client = MagicMock()
    prompt_client.prompt = _STUB_PROMPT_TEXT
    lf = MagicMock()
    lf.start_as_current_observation.return_value = span
    lf.get_prompt.return_value = prompt_client
    return lf


# ── _build_crispe ──────────────────────────────────────────────────────────────

def test_build_crispe_injects_recommendation_fields():
    crispe = _build_crispe(_RFC2119_REC, _STUB_CAPACITY, _STUB_PERSONALITY, _STUB_EXPERIMENT)
    assert crispe.role == _RFC2119_REC["role"]
    assert crispe.insight == _RFC2119_REC["insight"]
    assert _RFC2119_REC["statement"] in crispe.statement


def test_build_crispe_statement_contains_two_phase_prefix():
    crispe = _build_crispe(_RFC2119_REC, _STUB_CAPACITY, _STUB_PERSONALITY, _STUB_EXPERIMENT)
    assert "Phase 1" in crispe.statement
    assert "Phase 2" in crispe.statement
    assert "RFC 2119" in crispe.statement


def test_build_crispe_has_fixed_capacity_and_personality():
    crispe = _build_crispe(_RFC2119_REC, _STUB_CAPACITY, _STUB_PERSONALITY, _STUB_EXPERIMENT)
    assert "specification author" in crispe.capacity
    assert "Standards-conformant" in crispe.personality
    assert "[implied]" in crispe.experiment


def test_build_crispe_system_prompt_contains_all_fields():
    prompt = _build_crispe(_RFC2119_REC, _STUB_CAPACITY, _STUB_PERSONALITY, _STUB_EXPERIMENT).system_prompt()
    for section in ("CAPACITY:", "ROLE:", "INSIGHT:", "STATEMENT:", "PERSONALITY:", "EXPERIMENT:"):
        assert section in prompt


def test_parse_crispe_section_extracts_capacity():
    assert "specification author" in _parse_crispe_section(_STUB_PROMPT_TEXT, "CAPACITY")


def test_parse_crispe_section_extracts_personality():
    assert "Standards-conformant" in _parse_crispe_section(_STUB_PROMPT_TEXT, "PERSONALITY")


def test_parse_crispe_section_extracts_experiment():
    assert "[implied]" in _parse_crispe_section(_STUB_PROMPT_TEXT, "EXPERIMENT")


def test_parse_crispe_section_missing_returns_empty():
    assert _parse_crispe_section(_STUB_PROMPT_TEXT, "ROLE") == ""


# ── spec_specialist_node ───────────────────────────────────────────────────────

@patch("norma.graph.spec_specialist.Langfuse")
@patch("norma.graph.spec_specialist.httpx.Client")
def test_shell_stores_artefact_under_correct_key(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _mock_http(_RFC2119_CONTENT)
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_specialist_node(_BASE_STATE)

    assert "spec_artefacts" in result
    assert "rfc2119" in result["spec_artefacts"]
    assert result["spec_artefacts"]["rfc2119"] == _RFC2119_ARTEFACT


@patch("norma.graph.spec_specialist.Langfuse")
@patch("norma.graph.spec_specialist.httpx.Client")
def test_shell_returns_only_its_artefact_key(mock_client_cls, mock_langfuse_cls):
    """Node returns only its own key — the graph reducer merges parallel results."""
    mock_client_cls.return_value = _mock_http(_RFC2119_CONTENT)
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_specialist_node(_BASE_STATE)

    assert result == {"spec_artefacts": {"rfc2119": _RFC2119_ARTEFACT}}


@patch("norma.graph.spec_specialist.Langfuse")
@patch("norma.graph.spec_specialist.httpx.Client")
def test_shell_strips_markdown_fences(mock_client_cls, mock_langfuse_cls):
    fenced = f"## EXAMPLE\n{_RFC2119_EXAMPLE}\n\n## ARTEFACT\n```markdown\n{_RFC2119_ARTEFACT}\n```"
    mock_client_cls.return_value = _mock_http(fenced)
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_specialist_node(_BASE_STATE)

    assert not result["spec_artefacts"]["rfc2119"].startswith("```")
    assert "# Constraints" in result["spec_artefacts"]["rfc2119"]


@patch("norma.graph.spec_specialist.Langfuse")
@patch("norma.graph.spec_specialist.httpx.Client")
def test_shell_fallback_when_no_artefact_label(mock_client_cls, mock_langfuse_cls):
    """If model omits ## ARTEFACT, full response is stored rather than dropping output."""
    mock_client_cls.return_value = _mock_http(_RFC2119_ARTEFACT)
    mock_langfuse_cls.return_value = _mock_langfuse()

    result = spec_specialist_node(_BASE_STATE)

    assert "# Constraints" in result["spec_artefacts"]["rfc2119"]


@patch("norma.graph.spec_specialist.Langfuse")
@patch("norma.graph.spec_specialist.httpx.Client")
def test_shell_includes_language_in_langfuse_span_name(mock_client_cls, mock_langfuse_cls):
    mock_client_cls.return_value = _mock_http(_RFC2119_CONTENT)
    mock_lf = _mock_langfuse()
    mock_langfuse_cls.return_value = mock_lf

    spec_specialist_node(_BASE_STATE)

    call_kwargs = mock_lf.start_as_current_observation.call_args
    assert call_kwargs.kwargs["name"] == "spec_specialist.rfc2119"
