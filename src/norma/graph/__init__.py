"""
Norma LangGraph pipeline — REQ-003 dynamic specialist injection.

Graph shape:
  intake
    ├─ gherkin_specialist     (permanent, parallel with spec_advisor)
    └─ spec_advisor           (permanent, parallel with gherkin_specialist)
         └─ [Send × N]        (one per SpecRecommendation in spec_advice)
              └─ spec_specialist  (single shell node, N parallel invocations)
                   └─ cai_gate   (fan-in barrier — waits for all incoming edges)
                        ↓
                   END / revise gherkin_specialist / halt

Fan-out mechanics:
  - Static parallel: two add_edge calls from "intake" — LangGraph launches both
    gherkin_specialist and spec_advisor concurrently.
  - Dynamic parallel: _dispatch_specialists returns list[Send], each carrying
    the full state plus a different current_recommendation. LangGraph runs all
    spec_specialist invocations concurrently and fans their state updates into
    cai_gate once all complete.
  - If spec_advice is empty (Gherkin-only requirement), dispatch returns
    "cai_gate" directly — no specialist invocations.
"""

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from norma.graph.cai_gate import cai_gate_node, route_after_gate
from norma.graph.gherkin_specialist import gherkin_specialist_node
from norma.graph.intake import intake_node
from norma.graph.spec_advisor import spec_advisor_node
from norma.graph.spec_specialist import spec_specialist_node
from norma.graph.state import NormaState


def _dispatch_specialists(state: NormaState) -> list[Send] | str:
    """
    Conditional-edge function after spec_advisor.

    Returns one Send per SpecRecommendation, injecting current_recommendation
    into state so the shell knows which brief to execute. Recommendations with
    non-empty depends_on are dispatched in the same wave for now — sequencing
    will be enforced once we have multi-language chains that require it.

    Falls back to "cai_gate" when spec_advice is empty.
    """
    advice = state.get("spec_advice") or []
    sends = [
        Send("spec_specialist", {**state, "current_recommendation": rec})
        for rec in advice
    ]
    return sends if sends else "cai_gate"


def build_graph() -> StateGraph:
    g: StateGraph = StateGraph(NormaState)

    g.add_node("intake", intake_node)
    g.add_node("gherkin_specialist", gherkin_specialist_node)
    g.add_node("spec_advisor", spec_advisor_node)
    g.add_node("spec_specialist", spec_specialist_node)
    g.add_node("cai_gate", cai_gate_node)

    g.set_entry_point("intake")

    # Static parallel fan-out from intake
    g.add_edge("intake", "gherkin_specialist")
    g.add_edge("intake", "spec_advisor")

    # Gherkin flows directly to CAI gate (permanent artefact)
    g.add_edge("gherkin_specialist", "cai_gate")

    # Spec advisor fans out dynamically; all shell instances flow to cai_gate
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


pipeline = build_graph().compile()
