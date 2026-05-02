"""
providers/azure/serving/agents/foundry_agent.py
Azure AI Foundry Agent — single-agent and multi-agent implementations.

Single agent: Uses the Azure AI Projects SDK (azure-ai-projects) to create
  and run a Foundry agent with code interpreter + function tools.

Multi-agent: Orchestrates multiple Foundry agents in a sequential handoff
  pattern: Researcher → Analyst → Writer (mirrors the OSS CrewAI crew).

Usage:
    runner = AzureFoundryAgentRunner()
    output = runner.run(AgentInput(message="Summarise Q3 results", mode="single"))
"""
from __future__ import annotations

import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentThread,
    MessageRole,
    RunStatus,
    ToolDefinition,
)
from azure.identity import DefaultAzureCredential

from core.interfaces.agent_runner import AbstractAgentRunner, AgentInput, AgentOutput, AgentMode
from core.schemas.agent import AgentInput as SchemaAgentInput
from providers.azure.config.settings import get_azure_settings
from serving.guardrails.guardrail_runner import GuardrailRunner

_guardrails = GuardrailRunner()


class AzureFoundryAgentRunner(AbstractAgentRunner):
    """
    AbstractAgentRunner backed by Azure AI Foundry Agents.

    Single mode: one Foundry agent with search + code-interpreter tools.
    Multi mode:  three chained Foundry agents (researcher → analyst → writer).
    """

    MODEL = "gpt-4o"

    def __init__(self) -> None:
        s = get_azure_settings()
        self._client = AIProjectClient.from_connection_string(
            conn_str=s.azure_ai_project_connection_string,
            credential=DefaultAzureCredential(),
        )

    # ── AbstractAgentRunner ────────────────────────────────────────────────────

    def run(self, input: AgentInput) -> AgentOutput:
        guard = _guardrails.check_input(input.message)
        if not guard.allowed:
            return AgentOutput(response=f"Blocked: {guard.reason}", blocked=True,
                               block_reason=guard.reason, provider="azure")

        if input.mode == AgentMode.MULTI:
            return self._run_multi(input)
        return self._run_single(input)

    def list_tools(self) -> list[str]:
        return ["code_interpreter", "bing_grounding", "function:search_knowledge_base"]

    # ── Single agent ──────────────────────────────────────────────────────────

    def _run_single(self, input: AgentInput) -> AgentOutput:
        agent = self._client.agents.create_agent(
            model=self.MODEL,
            name="llmops-assistant",
            instructions=(
                "You are a helpful AI assistant. Use your tools to answer questions accurately. "
                "Always cite sources when retrieving information."
            ),
            tools=[{"type": "code_interpreter"}],
        )
        thread: AgentThread = self._client.agents.create_thread()
        self._client.agents.create_message(
            thread_id=thread.id,
            role=MessageRole.USER,
            content=input.message,
        )
        run = self._client.agents.create_and_process_run(
            thread_id=thread.id, agent_id=agent.id
        )
        response = self._get_last_assistant_message(thread.id)
        self._client.agents.delete_agent(agent.id)

        out_guard = _guardrails.check_output(response)
        return AgentOutput(
            response=out_guard.sanitised_text or response,
            session_id=thread.id,
            provider="azure",
        )

    # ── Multi-agent (sequential handoff) ─────────────────────────────────────

    def _run_multi(self, input: AgentInput) -> AgentOutput:
        """
        Three-agent sequential pipeline:
          1. Researcher gathers facts.
          2. Analyst synthesises findings.
          3. Writer produces final answer.
        """
        agents_spec = [
            ("researcher", "You are a research specialist. Gather relevant facts and data."),
            ("analyst", "You are a data analyst. Synthesise the researcher's findings."),
            ("writer", "You are a technical writer. Produce a clear, concise final answer."),
        ]

        context = input.message
        thread_ids: list[str] = []

        for name, instructions in agents_spec:
            agent = self._client.agents.create_agent(
                model=self.MODEL,
                name=f"llmops-{name}",
                instructions=instructions,
                tools=[{"type": "code_interpreter"}],
            )
            thread: AgentThread = self._client.agents.create_thread()
            thread_ids.append(thread.id)
            self._client.agents.create_message(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=context,
            )
            self._client.agents.create_and_process_run(
                thread_id=thread.id, agent_id=agent.id
            )
            context = self._get_last_assistant_message(thread.id)
            self._client.agents.delete_agent(agent.id)

        out_guard = _guardrails.check_output(context)
        return AgentOutput(
            response=out_guard.sanitised_text or context,
            session_id=thread_ids[-1] if thread_ids else "",
            provider="azure",
        )

    # ── Helper ────────────────────────────────────────────────────────────────

    def _get_last_assistant_message(self, thread_id: str) -> str:
        messages = self._client.agents.list_messages(thread_id=thread_id)
        for msg in reversed(messages.data):
            if msg.role == MessageRole.AGENT:
                for block in msg.content:
                    if hasattr(block, "text"):
                        return block.text.value
        return ""
