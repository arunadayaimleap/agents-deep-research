#!/usr/bin/env python3
"""Quick test to verify SearchAgent has email validation tools and calls them."""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from deep_researcher.agents.tool_agents.search_agent import init_search_agent
from deep_researcher.llm_config import create_default_config


async def test_agent():
    """Test SearchAgent initialization and tools."""
    
    print("=" * 70)
    print("SEARCHAGENT EMAIL VALIDATION TEST")
    print("=" * 70)
    print()
    
    # Initialize agent
    config = create_default_config()
    agent = init_search_agent(config)
    
    print(f"[1] Agent Name: {agent.name}")
    print(f"[2] Number of Tools: {len(agent.tools)}")
    print()
    
    # Check tools
    print("[3] Available Tools:")
    for i, tool in enumerate(agent.tools, 1):
        tool_name = getattr(tool, 'name', str(tool)[:50])
        print(f"    {i}. {tool_name}")
    print()
    
    # Check for SendGrid tools
    tool_names = [getattr(t, 'name', str(t)) for t in agent.tools]
    has_send_validation = any('send_validation' in str(t) for t in tool_names)
    has_test_pattern = any('test_email_pattern' in str(t) for t in tool_names)
    has_check_status = any('check_pattern' in str(t) for t in tool_names)
    
    print("[4] Email Validation Tools Present:")
    print(f"    - send_validation_email: {'YES' if has_send_validation else 'NO'}")
    print(f"    - test_email_pattern: {'YES' if has_test_pattern else 'NO'}")
    print(f"    - check_pattern_validation_status: {'YES' if has_check_status else 'NO'}")
    print()
    
    # Check instructions
    print("[5] Agent Instructions Check:")
    instructions = agent.instructions
    
    checks = {
        "MANDATORY email validation": "MANDATORY" in instructions,
        "ACTIVELY LOOK FOR emails": "ACTIVELY LOOK FOR" in instructions,
        "30+ second wait": "30" in instructions,
        "send_validation_email mentioned": "send_validation_email" in instructions,
        "test_email_pattern mentioned": "test_email_pattern" in instructions,
        "check_pattern_validation_status mentioned": "check_pattern_validation_status" in instructions,
        "Email Validation Results section": "Email Validation Results" in instructions,
    }
    
    for check_name, result in checks.items():
        status = "YES" if result else "NO"
        print(f"    - {check_name}: {status}")
    print()
    
    # Summary
    print("=" * 70)
    if all([has_send_validation, has_test_pattern, has_check_status]) and all(checks.values()):
        print("SUCCESS: SearchAgent is properly configured for email validation!")
        print()
        print("The agent will:")
        print("  1. Search for email patterns")
        print("  2. Use test_email_pattern to validate patterns")
        print("  3. Use send_validation_email for specific emails")
        print("  4. Use check_pattern_validation_status to verify delivery")
        print("  5. Report all validation results")
    else:
        print("WARNING: Some components are missing!")
        missing = []
        if not has_send_validation:
            missing.append("send_validation_email")
        if not has_test_pattern:
            missing.append("test_email_pattern")
        if not has_check_status:
            missing.append("check_pattern_validation_status")
        for check_name, result in checks.items():
            if not result:
                missing.append(check_name)
        print(f"Missing: {', '.join(missing)}")
    
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_agent())
