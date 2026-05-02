"""
serving/agents/supervisor_graph.py
LangGraph supervisor multi-agent system.

Architecture
------------
                    ┌─────────────┐
        ──────────► │  Supervisor │ ◄─────────────────────┐
                    └──────┬──────┘                        │
          ┌────────────────┼───────────────┐               │
          ▼                ▼               ▼               │
    ┌──────────┐   ┌──────────────┐  ┌──────────┐         │
    │   RAG    │   │  Calculator  │  │ General  │         │
    │  Agent   │   │    Agent     │  │  Agent   │         │
    └────┬─────┘   └──────┬───────┘  └────┬─────┘         │
         └────────────────┴───────────────┘                │
                          │  (result back to supervisor) ──┘

The Supervisor LLM reads the conversation and routes to one of:
    rag_agent | calculator_agent | general_agent | FINISH

Each worker runs its own ReAct loop and appends an AIMessage with its result.
The supervisor then decides the next step or terminates.

Usage:
    from serving.agents.supervisor_graph import run_supervisor

    answer = run_supervisor("What is the capital of France, and what is sqrt(144)?")
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from observability.tracing.tracer import get_tracer
from serving.guardrails.guardrail_runner import GuardrailRunner

log = structlog.get_logger()
tracer = get_tracer("supervisor_agent")
_guardrails = GuardrailRunner()

# Worker names — must match node names in the graph
WORKERS = ["rag_agent", "calculator_agent", "general_agent"]
RouteDecision = Literal["rag_agent", "calculator_agent", "general_agent", "FINISH"]


# ── Shared state ──────────────────────────────────────────────────────────────

class SupervisorState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    next: str          # routing decision from supervisor
    iteration: int     # guard against infinite loops


# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def search_knowledge_base(query: str) -> str:
    """Search internal knowledge base. Use for factual / domain-specific questions."""
    return f"[Knowledge base result for: {query}]"


@tool
def retrieve_document(doc_id: str) -> str:
    """Fetch a specific document by ID from the knowledge base."""
    return f"[Document {doc_id} content]"


@tool
def calculate(expression: str) -> str:
    """Evaluate a safe mathematical expression."""
    import ast
    try:
        tree = ast.parse(expression, mode="eval")
        allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                   ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.Mod}
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


@tool
def summarise(text: str) -> str:
    """Summarise a long piece of text into bullet points."""
    return f"[Summary of: {text[:80]}...]"


RAG_TOOLS = [search_knowledge_base, retrieve_document]
CALC_TOOLS = [calculate, get_current_date]
GENERAL_TOOLS = [get_current_date, summarise]


# ── Supervisor node ───────────────────────────────────────────────────────────

_SUPERVISOR_SYSTEM = f"""You are a supervisor coordinating a team of specialist AI agents.
Given the conversation so far, decide which agent should act next.

Available agents:
- rag_agent        — answers questions using the internal knowledge base and document retrieval
- calculator_agent — performs mathematical calculations and date/time operations
- general_agent    — handles general questions, summaries, and open-ended tasks

Respond with EXACTLY one of: {", ".join(WORKERS + ["FINISH"])}
Respond with FINISH when the user's question has been fully answered.
Do not add any explanation — output only the agent name or FINISH."""


def make_supervisor_node(llm: ChatOpenAI):
    def supervisor(state: SupervisorState) -> SupervisorState:
        if state["iteration"] >= 12:
            return {"next": "FINISH"}

        messages = [SystemMessage(content=_SUPERVISOR_SYSTEM)] + state["messages"]
        response = llm.invoke(messages)
        decision = response.content.strip()

        if decision not in WORKERS + ["FINISH"]:
            log.warning("supervisor_invalid_route", decision=decision)
            decision = "FINISH"

        return {"next": decision}

    return supervisor


# ── Worker node factory ───────────────────────────────────────────────────────

def make_worker_node(name: str, system_prompt: str, tools: list, llm: ChatOpenAI):
    """Returns a node function that runs a single ReAct step for the worker."""
    bound_llm = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def worker(state: SupervisorState) -> SupervisorState:
        worker_messages = [SystemMessage(content=system_prompt)] + state["messages"]

        with tracer.start_as_current_span(f"worker_{name}") as span:
            span.set_attribute("iteration", state["iteration"])
            response = bound_llm.invoke(worker_messages)

            # If the worker wants to use tools, execute one round of tool calls
            if getattr(response, "tool_calls", None):
                tool_result = tool_node.invoke({"messages": state["messages"] + [response]})
                tool_messages = tool_result["messages"]
                # Second pass: let the worker formulate a final answer with tool results
                final = bound_llm.invoke(
                    worker_messages + [response] + tool_messages
                )
                span.set_attribute("used_tools", True)
                return {
                    "messages": [final],
                    "iteration": state["iteration"] + 1,
                }

            span.set_attribute("used_tools", False)
            return {
                "messages": [response],
                "iteration": state["iteration"] + 1,
            }

    worker.__name__ = name
    return worker


# ── Graph construction ────────────────────────────────────────────────────────

def build_supervisor_graph() -> StateGraph:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    rag_node = make_worker_node(
        "rag_agent",
        "You are a RAG specialist. Answer using the knowledge base tools. "
        "Always cite retrieved content. Be concise.",
        RAG_TOOLS,
        llm,
    )
    calc_node = make_worker_node(
        "calculator_agent",
        "You are a calculation specialist. Use the calculate tool for any arithmetic. "
        "Show your work clearly.",
        CALC_TOOLS,
        llm,
    )
    general_node = make_worker_node(
        "general_agent",
        "You are a general-purpose assistant. Handle open-ended questions, "
        "summaries, and tasks not covered by other specialists.",
        GENERAL_TOOLS,
        llm,
    )

    supervisor_node = make_supervisor_node(llm)

    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("rag_agent", rag_node)
    graph.add_node("calculator_agent", calc_node)
    graph.add_node("general_agent", general_node)

    # Entry point is always the supervisor
    graph.set_entry_point("supervisor")

    # Supervisor routes to a worker or terminates
    graph.add_conditional_edges(
        "supervisor",
        lambda s: s["next"],
        {
            "rag_agent": "rag_agent",
            "calculator_agent": "calculator_agent",
            "general_agent": "general_agent",
            "FINISH": END,
        },
    )

    # Each worker reports back to supervisor
    for worker_name in WORKERS:
        graph.add_edge(worker_name, "supervisor")

    return graph.compile()


# ── Public entry point ────────────────────────────────────────────────────────

def run_supervisor(user_message: str) -> str:
    """
    Run the supervisor multi-agent graph on a user message.
    Returns the text of the last AI message produced.
    """
    # Input guardrail
    guard = _guardrails.check_input(user_message)
    if not guard.allowed:
        return f"Request blocked: {guard.reason}"

    agent = build_supervisor_graph()

    with tracer.start_as_current_span("supervisor_run") as span:
        span.set_attribute("message_len", len(user_message))
        result = agent.invoke({
            "messages": [HumanMessage(content=user_message)],
            "next": "",
            "iteration": 0,
        })

    # Find the last substantive AI message
    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    last = ai_messages[-1] if ai_messages else None
    output = last.content if last and hasattr(last, "content") else str(result)

    # Output guardrail
    out_guard = _guardrails.check_output(output)
    return out_guard.sanitised_text or output
