"""
providers/gcp/serving/agents/agent_engine.py
Vertex AI Agent Engine — single and multi-agent implementations.

Single agent: Deploys a ReasoningEngine (Agent Engine) backed by Gemini with
  function tools for knowledge base search and calculation.

Multi-agent: Orchestrates three sequential Gemini-powered agents
  (researcher → analyst → writer) using the generative models API directly,
  mirroring the OSS CrewAI crew and Azure Foundry multi-agent pipeline.

Usage:
    runner = VertexAgentRunner()
    output = runner.run(AgentInput(message="What drove revenue growth in Q3?", mode="multi"))
"""
from __future__ import annotations

import vertexai
from vertexai.generative_models import (
    FunctionDeclaration,
    GenerativeModel,
    Part,
    Tool,
)

from core.interfaces.agent_runner import AbstractAgentRunner, AgentInput, AgentOutput, AgentMode
from providers.gcp.config.settings import get_gcp_settings
from serving.guardrails.guardrail_runner import GuardrailRunner

_guardrails = GuardrailRunner()


# ── Tool declarations ──────────────────────────────────────────────────────────

_SEARCH_KB = FunctionDeclaration(
    name="search_knowledge_base",
    description="Search the internal knowledge base for relevant documents.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    },
)

_CALCULATE = FunctionDeclaration(
    name="calculate",
    description="Evaluate a safe mathematical expression.",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "Math expression"}},
        "required": ["expression"],
    },
)

_TOOLS = Tool(function_declarations=[_SEARCH_KB, _CALCULATE])


def _execute_tool(name: str, args: dict) -> str:
    """Dispatch function tool calls to local implementations."""
    if name == "search_knowledge_base":
        return f"[Knowledge base results for: {args.get('query', '')}]"
    if name == "calculate":
        import ast
        expr = args.get("expression", "")
        try:
            tree = ast.parse(expr, mode="eval")
            allowed = {ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                       ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub}
            for node in ast.walk(tree):
                if type(node) not in allowed:
                    return "Error: unsafe expression"
            return str(eval(compile(tree, "<string>", "eval")))
        except Exception as e:
            return f"Error: {e}"
    return f"Unknown tool: {name}"


class VertexAgentRunner(AbstractAgentRunner):
    """
    AbstractAgentRunner backed by Vertex AI Agent Engine (ReasoningEngine)
    for single-agent, and a sequential multi-agent pattern using Gemini
    generative models for multi-agent.
    """

    MODEL = "gemini-1.5-pro-002"
    MAX_TOOL_ITERATIONS = 8

    def __init__(self) -> None:
        s = get_gcp_settings()
        vertexai.init(project=s.gcp_project_id, location=s.gcp_region)
        self._settings = s

    def run(self, input: AgentInput) -> AgentOutput:
        guard = _guardrails.check_input(input.message)
        if not guard.allowed:
            return AgentOutput(response=f"Blocked: {guard.reason}", blocked=True,
                               block_reason=guard.reason, provider="gcp")

        if input.mode == AgentMode.MULTI:
            return self._run_multi(input)
        return self._run_single(input)

    def list_tools(self) -> list[str]:
        return ["search_knowledge_base", "calculate"]

    # ── Single ReAct agent ────────────────────────────────────────────────────

    def _run_single(self, input: AgentInput) -> AgentOutput:
        model = GenerativeModel(self.MODEL, tools=[_TOOLS])
        chat = model.start_chat()
        response = chat.send_message(input.message)
        iterations = 0

        while iterations < self.MAX_TOOL_ITERATIONS:
            tool_calls = [
                p.function_call
                for c in response.candidates
                for p in c.content.parts
                if p.function_call.name
            ]
            if not tool_calls:
                break

            tool_results = [
                Part.from_function_response(
                    name=tc.name,
                    response={"result": _execute_tool(tc.name, dict(tc.args))},
                )
                for tc in tool_calls
            ]
            response = chat.send_message(tool_results)
            iterations += 1

        final_text = response.text or ""
        out_guard = _guardrails.check_output(final_text)
        return AgentOutput(
            response=out_guard.sanitised_text or final_text,
            iterations=iterations,
            provider="gcp",
        )

    # ── Multi-agent (sequential pipeline) ────────────────────────────────────

    def _run_multi(self, input: AgentInput) -> AgentOutput:
        specialists = [
            ("researcher",
             "You are a research specialist. Gather relevant facts and data for the query."),
            ("analyst",
             "You are a data analyst. Synthesise the research into key insights."),
            ("writer",
             "You are a technical writer. Write a clear, concise final answer."),
        ]
        context = input.message
        iterations = 0

        for _, system_prompt in specialists:
            model = GenerativeModel(
                self.MODEL,
                system_instruction=system_prompt,
                tools=[_TOOLS],
            )
            response = model.generate_content(
                context,
                generation_config={"max_output_tokens": 1024, "temperature": 0.3},
            )
            context = response.text or context
            iterations += 1

        out_guard = _guardrails.check_output(context)
        return AgentOutput(
            response=out_guard.sanitised_text or context,
            iterations=iterations,
            provider="gcp",
        )
