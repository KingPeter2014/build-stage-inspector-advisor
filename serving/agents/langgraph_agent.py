"""
serving/agents/langgraph_agent.py
ReAct-style agent using LangGraph with tool use, tracing, and guardrail hooks.
"""
from __future__ import annotations

from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import operator

from observability.tracing.tracer import get_tracer
from serving.guardrails.guardrail_runner import GuardrailRunner

tracer = get_tracer("agent")
guardrails = GuardrailRunner()


# ── Agent state ────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    iteration: int
    blocked: bool


# ── Tool definitions ───────────────────────────────────────────────────────────

@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for relevant information."""
    # Wire to your QdrantVectorStore in production
    return f"[Knowledge base result for: {query}]"


@tool
def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression."""
    import ast
    try:
        tree = ast.parse(expression, mode="eval")
        # Only allow safe node types
        allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub}
        for node in ast.walk(tree):
            if type(node) not in allowed:
                return "Error: unsafe expression"
        return str(eval(compile(tree, "<string>", "eval")))
    except Exception as e:
        return f"Error: {e}"


@tool
def get_current_date() -> str:
    """Return today's date in ISO format."""
    from datetime import date
    return date.today().isoformat()


TOOLS = [search_knowledge_base, calculate, get_current_date]


# ── Node functions ─────────────────────────────────────────────────────────────

def call_model(state: AgentState) -> AgentState:
    """Invoke the LLM with current message history."""
    if state.get("blocked"):
        return state

    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)

    with tracer.start_as_current_span("agent_llm_call") as span:
        span.set_attribute("iteration", state["iteration"])
        response = llm.invoke(state["messages"])
        span.set_attribute("has_tool_calls", bool(getattr(response, "tool_calls", [])))

    return {
        "messages": [response],
        "iteration": state["iteration"] + 1,
        "blocked": False,
    }


def input_guardrail(state: AgentState) -> AgentState:
    """Run guardrails on the latest user message before LLM call."""
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    if last_human:
        result = guardrails.check_input(last_human.content)
        if not result.allowed:
            blocked_msg = AIMessage(content=f"I cannot process this request: {result.reason}")
            return {**state, "messages": [blocked_msg], "blocked": True}
    return state


def should_continue(state: AgentState) -> str:
    """Route: if last message has tool calls → tools, otherwise → END."""
    if state.get("blocked"):
        return END
    if state["iteration"] >= 10:          # Hard iteration limit
        return END
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Build graph ────────────────────────────────────────────────────────────────

def build_agent() -> StateGraph:
    tool_node = ToolNode(TOOLS)
    graph = StateGraph(AgentState)

    graph.add_node("guardrail", input_guardrail)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("guardrail")
    graph.add_edge("guardrail", "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def run_agent(user_message: str) -> str:
    """Convenience wrapper — returns the final text response."""
    agent = build_agent()
    result = agent.invoke({
        "messages": [HumanMessage(content=user_message)],
        "iteration": 0,
        "blocked": False,
    })
    final = result["messages"][-1]
    return final.content if hasattr(final, "content") else str(final)
