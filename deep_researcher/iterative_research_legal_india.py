"""
Iterative researcher configured for India legal news / analytical articles.

Uses LegalIndia knowledge-gap and tool-selector agents plus WebSearch, SiteCrawler, and
CourtSearch. On completion, `last_related_legal_topics` holds follow-on article ideas for
queueing (similar to MRO `last_related_targets`).

Model usage: `reasoning_model` for ThinkingAgent, LegalIndia knowledge-gap, and LegalIndia
tool-selector (planning and gap evaluation). `fast_model` for WebSearch, SiteCrawler,
CourtSearch, and EvidencePackerAgent (pre-writer dedupe). `main_model` only for WriterAgent (final `.md`).

Before the loop, **LegalIndiaCaseResolutionAgent** (`reasoning_model`) normalizes the matter from the
desk brief (verbatim ids only, suggested search seed); result is injected into BACKGROUND for all iterations.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from agents import gen_trace_id, trace

from .agents.baseclass import ResearchRunner
from .agents.evidence_packer_agent import init_evidence_packer_agent
from .agents.legal_india_case_resolution import (
    CaseResolutionOutput,
    init_legal_india_case_resolution_agent,
)
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
        max_iterations: int = 10,
        max_time_minutes: int = 30,
        verbose: bool = True,
        tracing: bool = False,
        config: Optional[LLMConfig] = None,
        *,
        pack_evidence_for_writer: bool = True,
        enable_case_resolution: bool = True,
    ):
        super().__init__(
            max_iterations=max_iterations,
            max_time_minutes=max_time_minutes,
            verbose=verbose,
            tracing=tracing,
            config=config,
            pack_evidence_for_writer=pack_evidence_for_writer,
        )
        self.enable_case_resolution: bool = enable_case_resolution
        self.config = create_default_config() if not config else config
        self.case_resolution_agent = init_legal_india_case_resolution_agent(self.config)
        self.knowledge_gap_agent = init_legal_india_knowledge_gap_agent(self.config)
        self.tool_selector_agent = init_legal_india_tool_selector_agent(self.config)
        self.thinking_agent = init_thinking_agent(self.config)
        self.tool_agents = init_tool_agents_legal_india(self.config)
        self.evidence_packer_agent = init_evidence_packer_agent(self.config)
        self.writer_agent = init_writer_agent(self.config)
        self.last_related_legal_topics: List[Dict] = []
        self.last_case_resolution: Optional[Dict] = None

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

    async def _select_agents(
        self,
        gap: str,
        query: str,
        background_context: str = "",
    ) -> AgentSelectionPlan:
        """Same as base class, but pass iteration number so the tool selector prioritizes diary/case ids on iteration 1."""
        background = f"BACKGROUND CONTEXT:\n{background_context}" if background_context else ""
        iter_preamble = f"Current Iteration Number: {self.iteration}\n\n"
        if self.iteration == 1:
            iter_preamble += (
                "FIRST-ITERATION WEB SEARCH MANDATE: WebSearchAgent queries MUST target retrieval of "
                "**diary number** (most important where listed), **case / registration / SLP / CA / appeal** "
                "numbers, or **cause list / listing** ids. Pair party names + court or tribunal + year with "
                "identifier keywords (diary no, case no, registration, listing). Avoid only broad headline "
                "queries without these terms.\n\n"
            )

        input_str = f"""
        {iter_preamble}
        ORIGINAL QUERY:
        {query}

        KNOWLEDGE GAP TO ADDRESS:
        {gap}

        {background}

        HISTORY OF ACTIONS, FINDINGS AND THOUGHTS:
        {self.conversation.compile_conversation_history() or "No previous actions, findings or thoughts available."}
        """

        result = await ResearchRunner.run(
            self.tool_selector_agent,
            input_str,
        )

        selection_plan = result.final_output_as(AgentSelectionPlan)

        self.conversation.set_latest_tool_calls([
            f"[Agent] {task.agent} [Query] {task.query} [Entity] {task.entity_website if task.entity_website else 'null'}"
            for task in selection_plan.tasks
        ])
        self._log_message(self.conversation.latest_action_string())

        return selection_plan

    async def _compile_evidence_brief(self, query: str) -> str:
        """Prepend structured case resolution so WriterAgent shares the same anchor as the loop."""
        core = await super()._compile_evidence_brief(query)
        if not self.last_case_resolution:
            return core
        head = (
            "## Case resolution (pre-research snapshot)\n\n"
            "Use this to keep one consistent matter; do not merge unrelated similarly named cases.\n\n"
            f"```json\n{json.dumps(self.last_case_resolution, indent=2, ensure_ascii=False)[:8000]}\n```\n\n"
            "--- EVIDENCE BRIEF (deduplicated tool output) ---\n\n"
        )
        return head + core

    @staticmethod
    def _format_case_resolution_background(
        base_background: str,
        res: CaseResolutionOutput,
    ) -> str:
        ids = ", ".join(res.normalized_identifiers) if res.normalized_identifiers else "(none in query text)"
        parties = ", ".join(res.parties_mentioned) if res.parties_mentioned else "(none extracted)"
        block = f"""--- CASE RESOLUTION (pre-research; reasoning-only from desk brief) ---
Status: {res.resolution_status}
Confidence: {res.confidence}
Canonical matter: {res.canonical_matter_label or "(not stated)"}
Court / forum: {res.court_or_forum or "(not stated)"}
Parties (extracted): {parties}
Timeframe: {res.rough_timeframe or "(not stated)"}
Identifiers verbatim from query: {ids}
Internal anchor id (slug, not a court number): {res.internal_anchor_id or "(none)"}
Suggested first search seed: {res.tool_search_seed}
Notes: {res.identifier_notes or "(none)"}
Disambiguation: {res.disambiguation_warning or "(none)"}
--- END CASE RESOLUTION ---"""
        if base_background and base_background.strip():
            return f"{base_background.strip()}\n\n{block}"
        return block

    async def _run_case_resolution(
        self,
        query: str,
        background_context: str,
    ) -> CaseResolutionOutput:
        payload = f"""DESK BRIEF (India legal article research)

{query}

RUNNER BACKGROUND (queue / ids, may be empty):
{background_context or "(none)"}

Task: produce CaseResolutionOutput JSON only. Do not search the web."""
        result = await ResearchRunner.run(self.case_resolution_agent, payload)
        return result.final_output_as(CaseResolutionOutput)

    async def run(
        self,
        query: str,
        output_length: str = "",
        output_instructions: str = "",
        background_context: str = "",
    ) -> str:
        self.start_time = time.time()
        self.last_related_legal_topics = []
        self.last_case_resolution = None
        workflow_trace = None

        if self.tracing:
            trace_id = gen_trace_id()
            workflow_trace = trace("iterative_researcher_india_legal", trace_id=trace_id)
            print(f"View trace: https://platform.openai.com/traces/trace?trace_id={trace_id}")
            workflow_trace.start(mark_as_current=True)

        self._log_message("=== Starting India Legal Iterative Research Workflow ===")

        research_background = background_context
        if self.enable_case_resolution:
            self._log_message("=== Case resolution (pre-loop, reasoning model) ===")
            try:
                cr = await self._run_case_resolution(query, background_context)
                self.last_case_resolution = cr.model_dump()
                research_background = self._format_case_resolution_background(background_context, cr)
                self._log_message(
                    f"[CASE RESOLUTION] status={cr.resolution_status} confidence={cr.confidence} "
                    f"anchor={cr.internal_anchor_id or '—'}"
                )
            except Exception as exc:
                self._log_message(f"[CASE RESOLUTION] skipped after error: {exc}")
                research_background = background_context
        else:
            research_background = background_context

        while self.should_continue and self._check_constraints():
            self.iteration += 1
            self._log_message(f"\n=== Starting Iteration {self.iteration} ===")

            self.conversation.add_iteration()

            await self._generate_observations(query, background_context=research_background)

            evaluation: LegalIndiaKnowledgeGapOutput = await self._evaluate_gaps(
                query, background_context=research_background
            )

            if not evaluation.research_complete:
                next_gap = evaluation.outstanding_gaps[0]
                selection_plan: AgentSelectionPlan = await self._select_agents(
                    next_gap, query, background_context=research_background
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
