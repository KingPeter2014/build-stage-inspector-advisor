"""
serving/agents/multiagent_crew.py
Multi-agent research crew built with CrewAI.

Crew composition (sequential pipeline):
  1. Researcher  — gathers relevant information from the knowledge base.
  2. Analyst     — synthesises findings, identifies gaps, draws conclusions.
  3. Writer      — produces a clear, well-structured final answer.

Hierarchy option:
  Set process=Process.hierarchical and provide a manager_llm to have CrewAI
  automatically spawn a manager agent that delegates and reviews work.

Usage:
    from serving.agents.multiagent_crew import run_crew

    answer = run_crew("Explain the impact of transformer architecture on NLP.")
"""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from crewai.tools import BaseTool
from pydantic import Field

from observability.tracing.tracer import get_tracer
from serving.guardrails.guardrail_runner import GuardrailRunner

tracer = get_tracer("crew_agent")
_guardrails = GuardrailRunner()


# ── Tools ─────────────────────────────────────────────────────────────────────

class KnowledgeBaseTool(BaseTool):
    name: str = "search_knowledge_base"
    description: str = (
        "Search the internal vector knowledge base for documents relevant to a query. "
        "Input: a search query string. Output: relevant text excerpts."
    )

    def _run(self, query: str) -> str:
        # Wire to QdrantVectorStore in production
        return f"[Knowledge base results for: {query}]"


class WebResearchTool(BaseTool):
    name: str = "web_research"
    description: str = (
        "Retrieve up-to-date information from the web for a given topic. "
        "Use only when the knowledge base lacks sufficient coverage."
    )

    def _run(self, topic: str) -> str:
        # Wire to a real search API (SerpAPI, Tavily, etc.) in production
        return f"[Web research results for: {topic}]"


class CalculatorTool(BaseTool):
    name: str = "calculate"
    description: str = "Safely evaluate a mathematical expression. Input: expression string."

    def _run(self, expression: str) -> str:
        import ast
        try:
            tree = ast.parse(expression, mode="eval")
            allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                       ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub}
            for node in ast.walk(tree):
                if type(node) not in allowed:
                    return "Error: unsafe expression"
            return str(eval(compile(tree, "<string>", "eval")))
        except Exception as e:
            return f"Error: {e}"


# ── Agent definitions ─────────────────────────────────────────────────────────

def _make_researcher() -> Agent:
    return Agent(
        role="Senior Research Specialist",
        goal=(
            "Gather comprehensive, accurate information from available sources. "
            "Prioritise the internal knowledge base; supplement with web research when needed."
        ),
        backstory=(
            "You are a meticulous researcher with deep expertise in information retrieval. "
            "You always cite sources, flag uncertainty, and never fabricate facts."
        ),
        tools=[KnowledgeBaseTool(), WebResearchTool()],
        verbose=True,
        allow_delegation=False,
    )


def _make_analyst() -> Agent:
    return Agent(
        role="Data Analyst",
        goal=(
            "Synthesise the researcher's findings into clear insights. "
            "Identify patterns, gaps, contradictions, and actionable conclusions."
        ),
        backstory=(
            "You are an analytical thinker who excels at turning raw information "
            "into structured, evidence-based insights. You use calculations when needed."
        ),
        tools=[CalculatorTool()],
        verbose=True,
        allow_delegation=False,
    )


def _make_writer() -> Agent:
    return Agent(
        role="Technical Writer",
        goal=(
            "Transform the analyst's conclusions into a concise, well-structured response "
            "that directly answers the user's original question."
        ),
        backstory=(
            "You are an expert communicator who can explain complex topics clearly "
            "to both technical and non-technical audiences. You never pad responses."
        ),
        tools=[],
        verbose=True,
        allow_delegation=False,
    )


# ── Task factory ──────────────────────────────────────────────────────────────

def _make_tasks(question: str, researcher: Agent, analyst: Agent, writer: Agent) -> list[Task]:
    research_task = Task(
        description=(
            f"Research the following question thoroughly:\n\n{question}\n\n"
            "Use the knowledge base first. Supplement with web research if needed. "
            "Return all relevant facts, data, and source references."
        ),
        expected_output=(
            "A structured summary of findings with source references, "
            "key facts highlighted, and any data gaps noted."
        ),
        agent=researcher,
    )

    analysis_task = Task(
        description=(
            "Analyse the research findings provided by the researcher. "
            "Identify the key insights, resolve any contradictions, and draw conclusions "
            "that directly address the original question."
        ),
        expected_output=(
            "A concise analytical summary with: key conclusions, supporting evidence, "
            "confidence level, and any remaining uncertainties."
        ),
        agent=analyst,
        context=[research_task],
    )

    writing_task = Task(
        description=(
            "Write the final answer to the user's question using the analyst's conclusions. "
            "Be clear, accurate, and appropriately detailed. "
            "Structure with headers if the answer is longer than three paragraphs."
        ),
        expected_output=(
            "A polished, complete answer to the original question, "
            "ready to be returned directly to the user."
        ),
        agent=writer,
        context=[analysis_task],
    )

    return [research_task, analysis_task, writing_task]


# ── Public entry point ────────────────────────────────────────────────────────

def build_crew(hierarchical: bool = False) -> Crew:
    """
    Construct the research crew.

    Parameters
    ----------
    hierarchical:
        When True, uses Process.hierarchical so CrewAI spawns a manager LLM
        to coordinate agents. Requires OPENAI_API_KEY or equivalent.
        When False (default), tasks run sequentially in pipeline order.
    """
    researcher = _make_researcher()
    analyst = _make_analyst()
    writer = _make_writer()

    # Tasks are built with a placeholder question; run_crew() injects the real one.
    tasks = _make_tasks("{question}", researcher, analyst, writer)

    return Crew(
        agents=[researcher, analyst, writer],
        tasks=tasks,
        process=Process.hierarchical if hierarchical else Process.sequential,
        verbose=True,
    )


def run_crew(question: str, hierarchical: bool = False) -> str:
    """
    Run the multi-agent crew on a user question and return the final answer.

    Parameters
    ----------
    question:
        The user's question or task description.
    hierarchical:
        Route through a manager agent for complex multi-step tasks.
    """
    # Input guardrail
    guard = _guardrails.check_input(question)
    if not guard.allowed:
        return f"Request blocked: {guard.reason}"

    researcher = _make_researcher()
    analyst = _make_analyst()
    writer = _make_writer()
    tasks = _make_tasks(question, researcher, analyst, writer)

    crew = Crew(
        agents=[researcher, analyst, writer],
        tasks=tasks,
        process=Process.hierarchical if hierarchical else Process.sequential,
        verbose=True,
    )

    with tracer.start_as_current_span("crew_run") as span:
        span.set_attribute("hierarchical", hierarchical)
        span.set_attribute("question_len", len(question))
        result = crew.kickoff(inputs={"question": question})
        span.set_attribute("output_len", len(str(result)))

    # Output guardrail
    out_text = str(result)
    out_guard = _guardrails.check_output(out_text)
    return out_guard.sanitised_text or out_text
