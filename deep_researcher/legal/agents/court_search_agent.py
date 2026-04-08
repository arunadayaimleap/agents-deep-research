"""
CourtSearchAgent: search Indian court/legal websites to resolve case citations.

Uses the same web search tool as WebSearchAgent but with instructions to query
indiankanoon.org, sci.gov.in, and other Indian legal sources.
"""

from ...agents.baseclass import ResearchAgent, ResearchRunner
from ...agents.tool_agents import ToolAgentOutput
from ...agents.utils.parse_output import create_type_parser
from ...llm_config import LLMConfig, model_supports_structured_output
from ...tools.document_tools import create_download_file_tool, create_read_pdf_tool
from ...tools.web_search import create_web_search_tool

INSTRUCTIONS = """You are a legal research assistant that finds Indian case law.

OBJECTIVE:
Given a citation or case name:
1. Use the web_search tool to search Indian legal sources
2. Prefer queries like: site:indiankanoon.org "<citation>"
   or site:scconline.com "<case name>" OR "<citation>" (digests, SCC Times, blog headnotes)
   or site:sci.gov.in "<case name>"
   or "AIR 1996 SC 1393" OR "(1996) 2 SCC 384"
3. Summarize what you found in **reporter-style detail** when available: full case title, all journal citations (SCC, AIR, SCALE, SCC OnLine tribunal reporters), court/tribunal, **coram (each judge’s full name as printed)**, decision date, case/appeal numbers, statutes and sections referred, catchwords or headnote subject lines, disposal, and **counsel (each advocate’s full name, designation, and party for whom they appeared)** if stated in the judgment header or body.

GUIDELINES:
- Use the web_search tool ONCE with a targeted query
- If results link a **PDF judgment or order**, use **download_file** then **read_pdf** on that file path to extract coram, counsel, citations, and holdings
- Focus on Indian Supreme Court, High Courts, and tribunals (indiankanoon.org, **scconline.com**, sci.gov.in, official tribunal sites)
- If the case is not found, say so clearly
- Output valid JSON with "output" (your summary) and "sources" (list of URLs or source names)
"""


def init_court_search_agent(config: LLMConfig) -> ResearchAgent:
    web_search_tool = create_web_search_tool(config)
    download_tool = create_download_file_tool(config)
    read_pdf_tool = create_read_pdf_tool(config)
    return ResearchAgent(
        name="CourtSearchAgent",
        instructions=INSTRUCTIONS,
        tools=[web_search_tool, download_tool, read_pdf_tool],
        model=config.fast_model,
        output_type=ToolAgentOutput if model_supports_structured_output(config.fast_model) else None,
        output_parser=create_type_parser(
            ToolAgentOutput,
            fallback_on_validation_error=lambda raw: ToolAgentOutput(output=raw, sources=[]),
        ) if not model_supports_structured_output(config.fast_model) else None,
    )
