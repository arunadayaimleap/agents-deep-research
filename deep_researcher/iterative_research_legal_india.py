"""
Iterative researcher configured for India legal news / analytical articles.

Uses LegalIndia knowledge-gap and tool-selector agents plus WebSearch, SiteCrawler, and
CourtSearch. On completion, `last_related_legal_topics` holds follow-on article ideas for
queueing (similar to MRO `last_related_targets`).
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from agents import gen_trace_id, trace

from .agents.baseclass import ResearchRunner
from .agents.legal_india_agents import (
    LegalIndiaKnowledgeGapOutput,
    init_legal_india_knowledge_gap_agent,
    init_legal_india_tool_selector_agent,
)
from .agents.thinking_agent import init_thinking_agent
from .agents.tool_agents import init_tool_agents_legal_india
from .agents.tool_selector_agent import AgentSelectionPlan
from .agents.writer_agent import init_writer_agent
from .iterative_research import IterativeResearcher
from .llm_config import LLMConfig, create_default_config


class IterativeResearcherIndiaLegal(IterativeResearcher):
    """Same loop as IterativeResearcher but India-legal agents and follow-on legal topics."""

    def __init__(
        self,
        max_iterations: int = 5,
        max_time_minutes: int = 30,
        verbose: bool = True,
        tracing: bool = False,
        config: Optional[LLMConfig] = None,
    ):
        super().__init__(
            max_iterations=max_iterations,
            max_time_minutes=max_time_minutes,
            verbose=verbose,
            tracing=tracing,
            config=config,
        )
        self.config = create_default_config() if not config else config
        self.knowledge_gap_agent = init_legal_india_knowledge_gap_agent(self.config)
        self.tool_selector_agent = init_legal_india_tool_selector_agent(self.config)
        self.thinking_agent = init_thinking_agent(self.config)
        self.tool_agents = init_tool_agents_legal_india(self.config)
        self.writer_agent = init_writer_agent(self.config)
        self.last_related_legal_topics: List[Dict] = []

    async def _evaluate_gaps(self, query: str, background_context: str = "") -> LegalIndiaKnowledgeGapOutput:
        import time as _time

        background = f"BACKGROUND CONTEXT:\n{background_context}" if background_context else ""

        input_str = f"""
        Current Iteration Number: {self.iteration}
        Time Elapsed: {(_time.time() - self.start_time) / 60:.2f} minutes of maximum {self.max_time_minutes} minutes

        ORIGINAL QUERY:
        {query}

        {background}

        HISTORY OF ACTIONS, FINDINGS AND THOUGHTS:
        {self.conversation.compile_conversation_history() or "No previous actions, findings or thoughts available."}
        """

        result = await ResearchRunner.run(
            self.knowledge_gap_agent,
            input_str,
        )

        evaluation = result.final_output_as(LegalIndiaKnowledgeGapOutput)

        if not evaluation.research_complete:
            next_gap = evaluation.outstanding_gaps[0]
            self.conversation.set_latest_gap(next_gap)
            self._log_message(self.conversation.latest_task_string())

        return evaluation

    async def run(
        self,
        query: str,
        output_length: str = "",
        output_instructions: str = "",
        background_context: str = "",
    ) -> str:
        self.start_time = time.time()
        self.last_related_legal_topics = []
        workflow_trace = None

        if self.tracing:
            trace_id = gen_trace_id()
            workflow_trace = trace("iterative_researcher_india_legal", trace_id=trace_id)
            print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}")
            workflow_trace.start(mark_as_current=True)

        self._log_message("=== Starting India Legal Iterative Research Workflow ===")

        while self.should_continue and self._check_constraints():
            self.iteration += 1
            self._log_message(f"\n=== Starting Iteration {self.iteration} ===")

            self.conversation.add_iteration()

            await self._generate_observations(query, background_context=background_context)

            evaluation: LegalIndiaKnowledgeGapOutput = await self._evaluate_gaps(
                query, background_context=background_context
            )

            if not evaluation.research_complete:
                next_gap = evaluation.outstanding_gaps[0]
                selection_plan: AgentSelectionPlan = await self._select_agents(
                    next_gap, query, background_context=background_context
                )
                await self._execute_tools(selection_plan.tasks)
            else:
                self.should_continue = False
                if evaluation.related_legal_topics:
                    self.last_related_legal_topics = [t.model_dump() for t in evaluation.related_legal_topics]
                self._log_message("=== India Legal Research Marked Complete — Finalizing Output ===")

        report = await self._create_final_report(query, length=output_length, instructions=output_instructions)

        elapsed_time = time.time() - self.start_time
        self._log_message(
            f"IterativeResearcherIndiaLegal completed in {int(elapsed_time // 60)} minutes and "
            f"{int(elapsed_time % 60)} seconds after {self.iteration} iterations."
        )

        if self.tracing and workflow_trace is not None:
            workflow_trace.finish(reset_current=True)

        return report
