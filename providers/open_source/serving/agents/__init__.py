"""
providers/open_source/serving/agents
Wires OSS agents to AbstractAgentRunner.
"""
from serving.agents import run_agent, run_crew, run_supervisor  # noqa: F401

from core.interfaces.agent_runner import AbstractAgentRunner, AgentInput, AgentOutput, AgentMode


class OSSAgentRunner(AbstractAgentRunner):
    """
    AbstractAgentRunner backed by:
      single — LangGraph ReAct agent  (serving.agents.langgraph_agent)
      multi  — CrewAI crew            (serving.agents.multiagent_crew)
               LangGraph supervisor   (serving.agents.supervisor_graph)
    """

    def run(self, input: AgentInput) -> AgentOutput:
        if input.mode == AgentMode.MULTI:
            # Default multi-agent: LangGraph supervisor (routes to specialists)
            response = run_supervisor(input.message)
        else:
            response = run_agent(input.message)

        return AgentOutput(
            response=response,
            session_id=input.session_id,
            provider="open_source",
        )

    def list_tools(self) -> list[str]:
        return ["search_knowledge_base", "calculate", "get_current_date"]
