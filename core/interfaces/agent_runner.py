"""
core/interfaces/agent_runner.py
Abstract agent runner contract for both single-agent and multi-agent modes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    SINGLE = "single"   # One ReAct agent with tools
    MULTI = "multi"     # Supervisor + specialist workers


@dataclass
class AgentInput:
    message: str
    session_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    mode: AgentMode = AgentMode.SINGLE


@dataclass
class AgentOutput:
    response: str
    session_id: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    blocked: bool = False
    block_reason: str = ""
    provider: str = ""


class AbstractAgentRunner(ABC):
    """
    Uniform interface for agent execution.
    Implementations:
      - OSS: LangGraph ReAct (single) + CrewAI / LangGraph Supervisor (multi)
      - Azure: Azure AI Foundry Agents
      - AWS: AWS AgentCore (Bedrock Agents)
      - GCP: Vertex AI Agent Engine
    """

    @abstractmethod
    def run(self, input: AgentInput) -> AgentOutput:
        """
        Execute the agent synchronously.
        Routes to single-agent or multi-agent orchestration based on input.mode.
        """

    @abstractmethod
    def list_tools(self) -> list[str]:
        """Return names of tools available to this agent."""
