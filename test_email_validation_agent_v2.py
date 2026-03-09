"""
Test script to verify EmailValidationAgent extracts real employee names from research findings.

This script tests if the agent correctly:
1. Parses research findings
2. Extracts real employee names
3. Identifies email pattern and domain
4. Constructs email addresses from real names
5. Tests those addresses with SendGrid
"""

import asyncio
import os
from deep_researcher.llm_config import LLMConfig
from deep_researcher.agents.tool_agents.email_validation_agent import init_email_validation_agent
from deep_researcher.agents.baseclass import ResearchRunner


async def test_email_validation_with_real_names():
    """Test the EmailValidationAgent with realistic research findings."""
    
    # Check for required API keys
    if not os.getenv("SENDGRID_API_KEY"):
        print("[ERROR] SENDGRID_API_KEY not set in .env")
        return
    
    if not os.getenv("OPENROUTER_API_KEY"):
        print("[ERROR] OPENROUTER_API_KEY not set in .env")
        return
    
    # Initialize config
    model = "openai/gpt-4o-mini"
    config = LLMConfig(
        search_provider="brightdata",
        reasoning_model_provider="openrouter",
        reasoning_model=model,
        main_model_provider="openrouter",
        main_model=model,
        fast_model_provider="openrouter",
        fast_model=model,
    )
    
    # Initialize the agent
    agent = init_email_validation_agent(config)
    print("\n" + "="*80)
    print("EMAIL VALIDATION AGENT TEST")
    print("="*80)
    
    print(f"\n[INIT] Agent initialized: {agent.name}")
    print(f"[INIT] Available tools: {[tool.name for tool in agent.tools]}")
    
    # Create a realistic test task with REAL employee and domain
    test_task = """
    Based on the research findings below, validate the email pattern:
    
    RESEARCH FINDINGS:
    
    ## Employee Found:
    - Arunaday Basu - Head of AI Research
    
    ## Real Email Example Found:
    arunadaybasu@gmail.com
    
    ## Email Pattern Identified:
    The pattern appears to be: firstname.lastname@gmail.com
    Example: arunadaybasu@gmail.com
    
    ## Company Domain:
    gmail.com
    
    Your task:
    1. Extract the real employee name: Arunaday Basu
    2. Use the identified pattern and domain
    3. Construct the email address: arunadaybasu@gmail.com
    4. Call validate_emails_full_workflow(email_addresses=["arunadaybasu@gmail.com"]) - it sends, waits 60s, checks delivery
    5. Report the result
    """
    
    print(f"\n[TASK] Starting validation task...")
    print(f"[TASK] Task details:\n{test_task}")
    
    try:
        # Run the agent using ResearchRunner
        print(f"\n[EXEC] Running agent...")
        result = await ResearchRunner.run(agent, test_task)
        
        print(f"\n" + "="*80)
        print("AGENT EXECUTION COMPLETE")
        print("="*80)
        
        print(f"\n[OUTPUT] Agent Result:")
        print(f"Type: {type(result)}")
        print(f"Final Output:\n{result.final_output}")
        
        # Try to get structured output
        try:
            from deep_researcher.agents.tool_agents import ToolAgentOutput
            structured = result.final_output_as(ToolAgentOutput)
            print(f"\n[STRUCTURED OUTPUT]")
            print(f"Output: {structured.output}")
            print(f"Sources: {structured.sources}")
        except Exception as e:
            print(f"\n[NOTE] Could not parse structured output: {e}")
        
    except Exception as e:
        print(f"\n[ERROR] Agent execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\nStarting EmailValidationAgent test...\n")
    asyncio.run(test_email_validation_with_real_names())
