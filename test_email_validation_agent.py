"""
Test script to demonstrate EmailValidationAgent calling tools.

This script initializes the EmailValidationAgent and gives it a task to validate
email addresses, showing all tool calls in action.
"""

import asyncio
import os
from deep_researcher.llm_config import LLMConfig
from deep_researcher.agents.tool_agents.email_validation_agent import init_email_validation_agent
from deep_researcher.agents.baseclass import ResearchRunner


async def test_email_validation_agent():
    """Test the EmailValidationAgent with a real email validation task."""
    
    # Check for required API keys
    if not os.getenv("SENDGRID_API_KEY"):
        print("[ERROR] SENDGRID_API_KEY not set in .env")
        return
    
    if not os.getenv("OPENROUTER_API_KEY"):
        print("[ERROR] OPENROUTER_API_KEY not set in .env")
        return
    
    # Initialize config with proper model
    model = "openai/gpt-4o-mini"
    config = LLMConfig(
        search_provider="jina",
        reasoning_model_provider="openrouter",
        reasoning_model=model,
        main_model_provider="openrouter",
        main_model=model,
        fast_model_provider="openrouter",
        fast_model=model,
    )
    
    print("\n" + "="*80)
    print("EMAIL VALIDATION AGENT TEST")
    print("="*80)
    
    # Initialize the agent
    agent = init_email_validation_agent(config)
    print(f"\n[INIT] Agent initialized: {agent.name}")
    print(f"[INIT] Available tools: {[tool.name for tool in agent.tools]}")
    
    # Create a test task
    test_task = """
    You have discovered the following employee at Example Corp:
    - Name: John Smith
    - Company: Example Corp
    - Domain: example.com
    
    Your task:
    1. Send validation emails to test the following email formats:
       - john.smith@example.com
       - jsmith@example.com
       - j.smith@example.com
    
    2. Wait 30 seconds for delivery
    
    3. Check the delivery status for each email
    
    4. Report which format(s) worked and which failed
    
    Output your findings as JSON with the validation results.
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
            structured = result.final_output_as("ToolAgentOutput")
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
    asyncio.run(test_email_validation_agent())
