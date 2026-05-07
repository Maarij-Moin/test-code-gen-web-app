"""LangGraph workflow orchestration for autonomous testing agents."""

from __future__ import annotations

import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.agents.generation_agent import generate_tests
from app.agents.planner_agent import plan_tests
from app.agents.pr_agent import build_pr_summary
from app.agents.retrieval_agent import retrieve_context
from app.agents.validation_agent import validate_tests
from app.services.diff_pipeline_service import run_diff_pipeline
from app.services.test_services import summarize_generated_tests


logger = logging.getLogger(__name__)


class AgentState(dict):
    """Mutable workflow state container for LangGraph."""


def _analyze_diff(state: AgentState) -> AgentState:
    repo_path = state["repo_path"]
    repo_id = state["repo_id"]
    logger.info("[agent_service] Running diff pipeline")
    diff_results = run_diff_pipeline(repo_path=repo_path, repo_id=repo_id)
    state["diff_results"] = diff_results
    return state


def _retrieve_context(state: AgentState) -> AgentState:
    repo_id = state["repo_id"]
    retrieval_map: dict[str, dict[str, list[Any]]] = {}
    for hunk in state.get("diff_results", []):
        key = f"{hunk.get('file')}:{hunk.get('function_name')}"
        query = f"{hunk.get('function_name')} {hunk.get('new_code', '')[:200]}"
        retrieval_map[key] = retrieve_context(repo_id=repo_id, query=query)
    state["retrieval_map"] = retrieval_map
    return state


def _plan_tests(state: AgentState) -> AgentState:
    plan = plan_tests(state.get("diff_results", []))
    state["plan"] = plan
    return state


def _generate_tests(state: AgentState) -> AgentState:
    artifacts = generate_tests(
        repo_path=state["repo_path"],
        diff_results=state.get("diff_results", []),
        retrieval_map=state.get("retrieval_map", {}),
        failure_logs=state.get("validation_output"),
    )
    state["generated_tests"] = artifacts
    return state


def _validate_tests(state: AgentState) -> AgentState:
    result = validate_tests(state["repo_path"])
    state["validation_status"] = result.status
    state["validation_output"] = result.output
    return state


def _should_retry(state: AgentState) -> str:
    attempts = state.get("repair_attempts", 0)
    if state.get("validation_status") == "failed" and attempts < 3:
        return "retry"
    return "continue"


def _increment_attempts(state: AgentState) -> AgentState:
    state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    return state


def _build_pr_summary(state: AgentState) -> AgentState:
    stats = summarize_generated_tests(state.get("diff_results", []))
    summary = build_pr_summary(
        repo_name=state.get("repo_name", "repository"),
        stats=stats,
        validation_status=state.get("validation_status", "unknown"),
    )
    state["pr_summary"] = summary
    return state


def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("analyze_diff", _analyze_diff)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("plan_tests", _plan_tests)
    graph.add_node("generate_tests", _generate_tests)
    graph.add_node("validate_tests", _validate_tests)
    graph.add_node("increment_attempts", _increment_attempts)
    graph.add_node("build_pr_summary", _build_pr_summary)

    graph.set_entry_point("analyze_diff")
    graph.add_edge("analyze_diff", "retrieve_context")
    graph.add_edge("retrieve_context", "plan_tests")
    graph.add_edge("plan_tests", "generate_tests")
    graph.add_edge("generate_tests", "validate_tests")

    graph.add_conditional_edges(
        "validate_tests",
        _should_retry,
        {"retry": "increment_attempts", "continue": "build_pr_summary"},
    )
    graph.add_edge("increment_attempts", "generate_tests")
    graph.add_edge("build_pr_summary", END)

    return graph


def run_agent_workflow(repo_path: str, repo_id: str, repo_name: str = "repository") -> Dict[str, Any]:
    """Run the LangGraph workflow and return the final state."""

    graph = build_agent_graph().compile()
    initial_state: AgentState = {
        "repo_path": repo_path,
        "repo_id": repo_id,
        "repo_name": repo_name,
        "repair_attempts": 0,
    }
    final_state = graph.invoke(initial_state)
    return dict(final_state)
