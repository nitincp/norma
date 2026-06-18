"""
Norma LangGraph pipeline — T1 → T2 → T3 → emit or revise.

Graph:
  intake_node → gherkin_specialist_node → cai_gate_node
                      ↑                        |
                      └── revise ──────────────┘
                                               |
                                          end / halt → END
"""

from langgraph.graph import END, StateGraph

from norma.graph.cai_gate import MAX_REVISIONS, cai_gate_node, route_after_gate
from norma.graph.gherkin_specialist import gherkin_specialist_node
from norma.graph.intake import intake_node
from norma.graph.state import NormaState


def build_graph() -> StateGraph:
    g = StateGraph(NormaState)

    g.add_node("intake", intake_node)
    g.add_node("gherkin_specialist", gherkin_specialist_node)
    g.add_node("cai_gate", cai_gate_node)

    g.set_entry_point("intake")
    g.add_edge("intake", "gherkin_specialist")
    g.add_edge("gherkin_specialist", "cai_gate")

    g.add_conditional_edges(
        "cai_gate",
        route_after_gate,
        {
            "end": END,
            "revise": "gherkin_specialist",
            "halt": END,
        },
    )

    return g


pipeline = build_graph().compile()
