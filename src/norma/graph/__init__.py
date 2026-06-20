"""
Norma — two-stage LangGraph pipeline (REQ-004).

Pipeline 1 — Business Layer:
  intake
    ├─ gherkin_specialist     (business Gherkin)
    └─ environment_advisor    (ranked environment options)
         └─ stage1_gate       (fan-in; promotes gherkin_business on pass)
              ↓ END

Pipeline 2 — Technical Layer:
  [initial state: gherkin_business + selected_environment + raw/normalised requirement]
    ├─ spec_advisor
    │    └─ [Send × N] → spec_specialist (dynamic, parallel)
    │                          └─ technical_gherkin_specialist (fan-in)
    │                                └─ stage2_gate
    │                                     ↓ END / revise / halt
    └─ (technical_gherkin_specialist also waits for spec_advisor fan-in)

The legacy `pipeline` export is preserved for backward compatibility with
existing smoke-test scripts; it compiles Pipeline 1 only.
"""

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from norma.graph.cai_gate import cai_gate_node, route_after_gate
from norma.graph.environment_advisor import environment_advisor_node
from norma.graph.gherkin_specialist import gherkin_specialist_node
from norma.graph.intake import intake_node
from norma.graph.spec_advisor import spec_advisor_node
from norma.graph.spec_specialist import spec_specialist_node
from norma.graph.stage1_gate import stage1_gate_node
from norma.graph.state import NormaState

# ---------------------------------------------------------------------------
# Pipeline 1 — Business Layer
# ---------------------------------------------------------------------------

def _build_pipeline1() -> StateGraph:
    """
    intake → [gherkin_specialist ‖ environment_advisor] → stage1_gate → END
    """
    g: StateGraph = StateGraph(NormaState)

    g.add_node("intake", intake_node)
    g.add_node("gherkin_specialist", gherkin_specialist_node)
    g.add_node("environment_advisor", environment_advisor_node)
    g.add_node("stage1_gate", stage1_gate_node)

    g.set_entry_point("intake")

    g.add_edge("intake", "gherkin_specialist")
    g.add_edge("intake", "environment_advisor")
    g.add_edge("gherkin_specialist", "stage1_gate")
    g.add_edge("environment_advisor", "stage1_gate")

    g.add_edge("stage1_gate", END)

    return g


pipeline1 = _build_pipeline1().compile()


# ---------------------------------------------------------------------------
# Pipeline 2 — Technical Layer
# ---------------------------------------------------------------------------

def _dispatch_specialists_p2(state: NormaState) -> list[Send] | str:
    """Pipeline 2 dispatch — falls back to technical_gherkin_specialist."""
    advice = state.get("spec_advice") or []
    sends = [
        Send("spec_specialist", {**state, "current_recommendation": rec})
        for rec in advice
    ]
    return sends if sends else "technical_gherkin_specialist"


def _dispatch_specialists(state: NormaState) -> list[Send] | str:
    """Legacy pipeline dispatch — falls back to cai_gate."""
    advice = state.get("spec_advice") or []
    sends = [
        Send("spec_specialist", {**state, "current_recommendation": rec})
        for rec in advice
    ]
    return sends if sends else "cai_gate"


def _build_pipeline2() -> StateGraph:
    """
    [gherkin_business + selected_environment]
      ├─ spec_advisor → Send(spec_specialist) × N
      │                       └─ technical_gherkin_specialist (fan-in)
      └─ (direct edge to technical_gherkin_specialist when no specialists)
           └─ stage2_gate → END / revise(technical_gherkin_specialist) / halt
    """
    # Import here to avoid circular import at module level
    from norma.graph.stage2_gate import route_after_stage2, stage2_gate_node
    from norma.graph.technical_gherkin_specialist import technical_gherkin_specialist_node

    g: StateGraph = StateGraph(NormaState)

    g.add_node("spec_advisor", spec_advisor_node)
    g.add_node("spec_specialist", spec_specialist_node)
    g.add_node("technical_gherkin_specialist", technical_gherkin_specialist_node)
    g.add_node("stage2_gate", stage2_gate_node)

    g.set_entry_point("spec_advisor")

    g.add_conditional_edges(
        "spec_advisor",
        _dispatch_specialists_p2,
        {
            "spec_specialist": "spec_specialist",
            "technical_gherkin_specialist": "technical_gherkin_specialist",
        },
    )
    g.add_edge("spec_specialist", "technical_gherkin_specialist")

    g.add_conditional_edges(
        "stage2_gate",
        route_after_stage2,
        {
            "end": END,
            "revise": "technical_gherkin_specialist",
            "halt": END,
        },
    )
    g.add_edge("technical_gherkin_specialist", "stage2_gate")

    return g


def build_pipeline2() -> object:
    """Build and compile Pipeline 2. Called lazily to avoid import order issues."""
    return _build_pipeline2().compile()


# ---------------------------------------------------------------------------
# Legacy export — Pipeline 1 as `pipeline` for backward-compat smoke tests
# ---------------------------------------------------------------------------

def _build_legacy() -> StateGraph:
    """
    Original single-pipeline shape kept for backward-compat (run_pipeline.py etc).
    intake → [gherkin_specialist ‖ spec_advisor → spec_specialist(s)] → cai_gate
    """
    g: StateGraph = StateGraph(NormaState)

    g.add_node("intake", intake_node)
    g.add_node("gherkin_specialist", gherkin_specialist_node)
    g.add_node("spec_advisor", spec_advisor_node)
    g.add_node("spec_specialist", spec_specialist_node)
    g.add_node("cai_gate", cai_gate_node)

    g.set_entry_point("intake")

    g.add_edge("intake", "gherkin_specialist")
    g.add_edge("intake", "spec_advisor")
    g.add_edge("gherkin_specialist", "cai_gate")

    g.add_conditional_edges(
        "spec_advisor",
        _dispatch_specialists,
        {"spec_specialist": "spec_specialist", "cai_gate": "cai_gate"},
    )
    g.add_edge("spec_specialist", "cai_gate")

    g.add_conditional_edges(
        "cai_gate",
        route_after_gate,
        {"end": END, "revise": "gherkin_specialist", "halt": END},
    )

    return g


pipeline = _build_legacy().compile()


def build_graph() -> StateGraph:
    """Kept for backward compat — returns the legacy single-pipeline StateGraph."""
    return _build_legacy()
