"""
LangGraph state shared across all Norma pipeline nodes.
"""

from typing import NotRequired, TypedDict


class NormaState(TypedDict, total=False):
    # T1 — INTAKE
    raw_requirement: str
    normalised_requirement: str
    actors: list[str]
    external_deps: list[str]

    # T2 — GHERKIN SPECIALIST
    gherkin_content: NotRequired[str]

    # T3 — NFR SPECIALIST
    nfr_content: NotRequired[str]

    # T4 — CAI GATE
    gate_passed: NotRequired[bool]
    gate_feedback: NotRequired[str]
    revision_count: NotRequired[int]
