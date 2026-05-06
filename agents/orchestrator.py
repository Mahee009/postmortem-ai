"""
orchestrator.py — LangGraph graph that runs the full PostMortemAI pipeline
State flows through: classify → retrieve → synthesize → output
"""

import os
import logging
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

from agents.classifier import classify_startup
from agents.matcher import retrieve_similar_failures
from agents.synthesizer import synthesize_risk_report

load_dotenv()
logger = logging.getLogger(__name__)


# ── State schema ─────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    user_message: str                    # Raw user description

    # Built during classification
    startup_profile: dict                # Structured startup profile
    classification_complete: bool

    # Retrieved from Qdrant
    similar_failures: list[dict]         # Top 15 similar postmortems
    retrieval_complete: bool

    # Final output
    risk_report: str                     # Markdown risk report
    source_postmortems: list[dict]       # The postmortems used as evidence
    error: str                           # Any error message


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def classify_node(state: AgentState) -> AgentState:
    """Turn the user's raw description into a structured startup profile."""
    logger.info("→ classify_node")
    try:
        profile = await classify_startup(state["user_message"])
        return {
            **state,
            "startup_profile": profile,
            "classification_complete": True,
        }
    except Exception as e:
        logger.error(f"classify_node failed: {e}")
        return {**state, "error": f"Classification failed: {str(e)}"}


async def retrieve_node(state: AgentState) -> AgentState:
    """Retrieve the 15 most similar startup failures from Qdrant."""
    logger.info("→ retrieve_node")
    if state.get("error"):
        return state
    try:
        profile = state["startup_profile"]
        failures = await retrieve_similar_failures(profile)
        return {
            **state,
            "similar_failures": failures,
            "retrieval_complete": True,
        }
    except Exception as e:
        logger.error(f"retrieve_node failed: {e}")
        return {**state, "error": f"Retrieval failed: {str(e)}"}


async def synthesize_node(state: AgentState) -> AgentState:
    """Generate the personalized risk report from profile + similar failures."""
    logger.info("→ synthesize_node")
    if state.get("error"):
        return state
    try:
        report, sources = await synthesize_risk_report(
            startup_profile=state["startup_profile"],
            similar_failures=state["similar_failures"],
        )
        return {
            **state,
            "risk_report": report,
            "source_postmortems": sources,
        }
    except Exception as e:
        logger.error(f"synthesize_node failed: {e}")
        return {**state, "error": f"Synthesis failed: {str(e)}"}


def should_continue(state: AgentState) -> str:
    """Route to END if there's an error."""
    if state.get("error"):
        return END
    return "continue"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("synthesize", synthesize_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Singleton graph instance
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

async def run_analysis(user_message: str, thread_id: str = "default") -> dict:
    """
    Main entry point. Run the full PostMortemAI pipeline.

    Args:
        user_message: Plain English description of the user's startup
        thread_id: Unique ID for this analysis session

    Returns:
        dict with keys: risk_report, startup_profile, source_postmortems, error
    """
    graph = get_graph()

    initial_state: AgentState = {
        "user_message": user_message,
        "startup_profile": {},
        "classification_complete": False,
        "similar_failures": [],
        "retrieval_complete": False,
        "risk_report": "",
        "source_postmortems": [],
        "error": "",
    }

    config = {"configurable": {"thread_id": thread_id}}

    final_state = await graph.ainvoke(initial_state, config=config)

    return {
        "risk_report": final_state.get("risk_report", ""),
        "startup_profile": final_state.get("startup_profile", {}),
        "source_postmortems": final_state.get("source_postmortems", []),
        "similar_failures_count": len(final_state.get("similar_failures", [])),
        "error": final_state.get("error", ""),
    }


if __name__ == "__main__":
    import asyncio

    test_input = """
    I'm building a B2B SaaS tool that helps freelancers track their time and invoice clients.
    6 months in, bootstrapped, team of 2. Have about 50 beta users but only 3 paying.
    My biggest worry is that we're not converting free users to paid.
    """

    result = asyncio.run(run_analysis(test_input))
    print("\n" + "="*60)
    print(result["risk_report"])
    print("="*60)
    print(f"\nBased on {result['similar_failures_count']} similar startup failures")
