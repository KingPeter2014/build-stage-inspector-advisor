"""
providers/aws/serving/agents/agentcore.py
AWS AgentCore / Amazon Bedrock Agents — single and multi-agent implementations.

Single agent: Invokes a pre-configured Bedrock Agent via InvokeAgent API.
Multi-agent: Uses AWS AgentCore supervisor pattern — a coordinator agent
  delegates to specialist sub-agents (researcher, analyst, writer) using
  the Bedrock Agents InlineAgent API (no pre-provisioning required).

Usage:
    runner = AWSAgentCoreRunner()
    output = runner.run(AgentInput(message="What are our Q3 revenue trends?", mode="single"))
"""
from __future__ import annotations

import json
import uuid

import boto3

from core.interfaces.agent_runner import AbstractAgentRunner, AgentInput, AgentOutput, AgentMode
from providers.aws.config.settings import get_aws_settings
from serving.guardrails.guardrail_runner import GuardrailRunner

_guardrails = GuardrailRunner()


class AWSAgentCoreRunner(AbstractAgentRunner):
    """
    AbstractAgentRunner backed by AWS AgentCore / Amazon Bedrock Agents.

    Single mode: Invokes a deployed Bedrock Agent (requires BEDROCK_AGENT_ID).
    Multi mode:  Orchestrates inline sub-agents via the Bedrock Converse API
                 with a supervisor prompt that routes between specialists.
    """

    def __init__(self) -> None:
        s = get_aws_settings()
        self._settings = s
        self._agent_client = boto3.client("bedrock-agent-runtime", region_name=s.aws_region)
        self._bedrock = boto3.client("bedrock-runtime", region_name=s.aws_region)

    def run(self, input: AgentInput) -> AgentOutput:
        guard = _guardrails.check_input(input.message)
        if not guard.allowed:
            return AgentOutput(response=f"Blocked: {guard.reason}", blocked=True,
                               block_reason=guard.reason, provider="aws")

        if input.mode == AgentMode.MULTI:
            return self._run_multi(input)
        return self._run_single(input)

    def list_tools(self) -> list[str]:
        return ["knowledge_base_retrieval", "code_interpreter", "web_search"]

    # ── Single agent (pre-deployed Bedrock Agent) ─────────────────────────────

    def _run_single(self, input: AgentInput) -> AgentOutput:
        session_id = input.session_id or str(uuid.uuid4())
        response = self._agent_client.invoke_agent(
            agentId=self._settings.bedrock_agent_id,
            agentAliasId=self._settings.bedrock_agent_alias_id,
            sessionId=session_id,
            inputText=input.message,
        )

        # Stream completion — collect all chunks
        completion = ""
        for event in response.get("completion", []):
            chunk = event.get("chunk", {})
            if "bytes" in chunk:
                completion += chunk["bytes"].decode("utf-8")

        out_guard = _guardrails.check_output(completion)
        return AgentOutput(
            response=out_guard.sanitised_text or completion,
            session_id=session_id,
            provider="aws",
        )

    # ── Multi-agent (inline supervisor + specialist agents) ───────────────────

    def _run_multi(self, input: AgentInput) -> AgentOutput:
        """
        Supervisor pattern via Bedrock Converse API (no pre-provisioning).
        Specialist roles: researcher → analyst → writer.
        """
        specialists = [
            ("researcher",
             "You are a research specialist. Gather facts relevant to the user's question."),
            ("analyst",
             "You are a data analyst. Analyse the provided research and draw conclusions."),
            ("writer",
             "You are a technical writer. Write a clear, concise answer based on the analysis."),
        ]

        context = input.message
        iterations = 0

        for role, system_prompt in specialists:
            response = self._bedrock.converse(
                modelId=self._settings.bedrock_model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": context}]}],
                inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
            )
            context = response["output"]["message"]["content"][0]["text"]
            iterations += 1

        out_guard = _guardrails.check_output(context)
        return AgentOutput(
            response=out_guard.sanitised_text or context,
            iterations=iterations,
            provider="aws",
        )
