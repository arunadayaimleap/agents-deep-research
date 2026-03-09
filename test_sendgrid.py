#!/usr/bin/env python3
"""
Test script for SendGrid email validation tools.

Tests:
1. Send a test email to a known address
2. Check delivery status
3. Validate an email pattern with multiple test addresses
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from deep_researcher.tools.sendgrid_tools import (
    send_test_email,
    check_email_delivery,
    validate_email_pattern,
)


async def main():
    # Check if SendGrid API key is configured
    api_key = os.getenv("SENDGRID_API_KEY")
    sender_email = os.getenv("SENDGRID_SENDER_EMAIL", "noreply@deepresearch.dev")

    if not api_key:
        print("[ERROR] SENDGRID_API_KEY not configured in .env")
        print("\nTo use SendGrid tools:")
        print("1. Get API key from https://app.sendgrid.com/settings/api_keys")
        print("2. Add to .env:")
        print("   SENDGRID_API_KEY=<your-api-key>")
        print("   SENDGRID_SENDER_EMAIL=<your-sender-email>")
        return

    print(f"SendGrid Configuration:")
    print(f"  API Key: {api_key[:20]}...")
    print(f"  Sender Email: {sender_email}")
    print()

    # Test 1: Send a test email to yourself
    print("[Test 1] Sending test email to validate basic functionality...")
    test_email = "test@example.com"  # Using example domain for demo
    result = await send_test_email(test_email)
    print(f"  Recipient: {result.get('email')}")
    print(f"  Status: {result.get('status')}")
    print(f"  Message: {result.get('message')}")
    print(f"  Validated: {result.get('validated')}")
    print()

    # Test 2: Check delivery status (will likely show no results since we just sent)
    print("[Test 2] Checking delivery status...")
    delivery = await check_email_delivery(test_email, hours_back=1)
    print(f"  Email: {delivery.get('email')}")
    print(f"  Status: {delivery.get('status')}")
    print(f"  Message: {delivery.get('message')}")
    print()

    # Test 3: Validate an email pattern
    print("[Test 3] Validating email pattern...")
    pattern_result = await validate_email_pattern(
        base_email="john.doe@company.com",
        pattern="firstname.lastname@company.com",
        test_names=["jane.smith", "bob.jones", "alice.brown"],
        company_domain="company.com",
    )
    print(f"  Pattern: {pattern_result.get('pattern')}")
    print(f"  Domain: {pattern_result.get('domain')}")
    print(f"  Total Tests: {pattern_result.get('total_tests')}")
    print(f"  Successful: {pattern_result.get('successful_validations')}")
    print(f"  Validation Rate: {pattern_result.get('validation_rate')*100:.1f}%")
    print()

    print("[INFO] Test completed. Check your SendGrid dashboard for email delivery status.")
    print()
    print("SendGrid Dashboard:")
    print("  1. Go to https://app.sendgrid.com")
    print("  2. Check 'Mail Activity' to see sent emails")
    print("  3. Monitor delivery, bounce, and engagement rates")


if __name__ == "__main__":
    asyncio.run(main())
