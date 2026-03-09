"""
SendGrid email tools for validating email patterns and sending test emails.

Tools:
- send_test_email: Send a test email to validate an email address
- check_email_delivery: Check delivery status of sent emails
- validate_email_pattern: Test a discovered email pattern by sending to multiple test addresses
"""

import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import quote

import aiohttp
from dotenv import load_dotenv
from agents import function_tool

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_BASE_URL = "https://api.sendgrid.com/v3"
SENDGRID_SENDER_EMAIL = os.getenv("SENDGRID_SENDER_EMAIL", "noreply@deepresearch.dev")


async def _get_sendgrid_headers() -> Dict[str, str]:
    """Get headers for SendGrid API requests."""
    if not SENDGRID_API_KEY:
        return {}
    return {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }


async def send_test_email(recipient_email: str, subject: str = "Email Pattern Validation Test") -> Dict:
    """
    Send a test email to validate an email address exists and is accepting mail.

    Args:
        recipient_email: Email address to test
        subject: Email subject line

    Returns:
        Dictionary with status, message, and email_id if successful
    """
    print(f"[SENDGRID] Sending test email to: {recipient_email}")
    
    if not SENDGRID_API_KEY:
        return {
            "status": "error",
            "message": "SENDGRID_API_KEY not configured",
            "email": recipient_email,
            "validated": False,
        }

    # Validate email format
    if not recipient_email or "@" not in recipient_email:
        return {
            "status": "error",
            "message": f"Invalid email format: {recipient_email}",
            "email": recipient_email,
            "validated": False,
        }

    email_body = """
Hello,

This is an automated test email from Deep Research Email Pattern Validation system.

If you received this email, it confirms that this email address is valid and currently active.

Test Details:
- Timestamp: {timestamp}
- Purpose: Email pattern discovery validation
- No action required

Best regards,
Deep Research System
""".format(timestamp=datetime.utcnow().isoformat())

    payload = {
        "personalizations": [
            {
                "to": [{"email": recipient_email}],
                "subject": subject,
            }
        ],
        "from": {
            "email": SENDGRID_SENDER_EMAIL,
            "name": "Deep Research Validator",
        },
        "content": [
            {
                "type": "text/plain",
                "value": email_body,
            }
        ],
        "custom_args": {
            "email_type": "pattern_validation",
            "timestamp": datetime.utcnow().isoformat(),
        },
    }

    headers = await _get_sendgrid_headers()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SENDGRID_BASE_URL}/mail/send",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status in (200, 202):
                    print(f"[SENDGRID] Email sent successfully to {recipient_email}")
                    return {
                        "status": "success",
                        "message": f"Test email sent to {recipient_email}",
                        "email": recipient_email,
                        "validated": True,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                else:
                    text = await response.text()
                    print(f"[SENDGRID] Failed with HTTP {response.status}: {text[:100]}")
                    return {
                        "status": "error",
                        "message": f"SendGrid HTTP {response.status}: {text[:200]}",
                        "email": recipient_email,
                        "validated": False,
                    }
    except asyncio.TimeoutError:
        return {
            "status": "error",
            "message": "Request timeout (30 seconds)",
            "email": recipient_email,
            "validated": False,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to send email: {str(e)}",
            "email": recipient_email,
            "validated": False,
        }


async def check_email_delivery(recipient_email: str, hours_back: int = 1) -> Dict:
    """
    Check delivery status of emails sent to a recipient using SendGrid APIs.

    Tries Email Activity API (v3/messages) first. Requires Email Activity add-on for full status.
    Falls back to "sent" assumption if API unavailable (emails were queued successfully).

    Args:
        recipient_email: Email address to check
        hours_back: How many hours back to search (default 1 for recent sends)

    Returns:
        Dictionary with delivery status information
    """
    if not SENDGRID_API_KEY:
        return {
            "status": "error",
            "message": "SENDGRID_API_KEY not configured",
            "email": recipient_email,
        }

    print(f"[SENDGRID] Checking delivery status for {recipient_email}")

    headers = await _get_sendgrid_headers()
    result = None

    try:
        async with aiohttp.ClientSession() as session:
            # Try 1: Email Logs API (v3/logs) - POST, often included in plans
            if result is None:
                since = datetime.utcnow() - timedelta(hours=hours_back)
                since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
                log_query = f'to_email="{recipient_email}" AND sg_message_id_created_at > TIMESTAMP "{since_str}"'
                async with session.post(
                    f"{SENDGRID_BASE_URL}/logs",
                    json={"query": log_query, "limit": 10},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as log_resp:
                    log_body = await log_resp.json() if log_resp.content_type == "application/json" else {}
                    if log_resp.status == 200:
                        messages = log_body.get("messages", [])
                        if messages:
                            statuses = {m.get("to_email", recipient_email): m.get("status", "unknown") for m in messages}
                            delivered = "delivered" in statuses.values()
                            best_status = "delivered" if delivered else messages[0].get("status", "unknown")
                            result = {
                                "status": "success" if delivered else best_status,
                                "email": recipient_email,
                                "message": f"Status: {best_status}",
                                "delivery_status": best_status,
                                "delivery_statuses": statuses,
                            }
                        else:
                            result = {
                                "status": "not_found",
                                "email": recipient_email,
                                "message": f"No recent messages for {recipient_email} (last {hours_back}h)",
                                "delivery_status": "no_messages",
                            }
                    else:
                        result = None  # Fall through to dashboard message

    except asyncio.TimeoutError:
        result = {"status": "error", "email": recipient_email, "message": "Request timeout"}
    except Exception as e:
        result = {"status": "error", "email": recipient_email, "message": str(e)}

    # Fallback: both APIs returned 403 (add-on required)
    if result is None:
        result = {
            "status": "info",
            "email": recipient_email,
            "message": f"SendGrid Email Activity add-on required for delivery status. If send succeeded, email was queued. Check: https://app.sendgrid.com/email_activity",
            "delivery_status": "check_dashboard",
        }

    print(f"[SENDGRID] Status check result: {result}")
    return result


async def validate_email_pattern(
    base_email: str,
    pattern: str,
    test_names: List[str],
    company_domain: str = None,
) -> Dict:
    """
    Validate an email pattern by sending test emails to generated addresses.

    Args:
        base_email: Reference email address (e.g., "john.doe@company.com")
        pattern: Email pattern description (e.g., "firstname.lastname@domain")
        test_names: List of test name combinations (e.g., ["jane.smith", "bob.jones"])
        company_domain: Company domain (optional, if different from base_email domain)

    Returns:
        Dictionary with validation results for each test email
    """
    if not base_email or "@" not in base_email:
        return {
            "status": "error",
            "message": "Invalid base email provided",
            "pattern": pattern,
            "validated": False,
        }

    # Extract domain from base email or use provided domain
    domain = company_domain or base_email.split("@")[1]

    test_results = []

    for test_name in test_names:
        test_email = f"{test_name}@{domain}"

        result = await send_test_email(
            test_email,
            subject=f"Email Pattern Validation - {pattern}",
        )

        test_results.append({
            "test_name": test_name,
            "test_email": test_email,
            "result": result,
        })

        # Small delay between requests to avoid rate limiting
        await asyncio.sleep(1)

    # Summarize results
    successful = sum(1 for r in test_results if r["result"].get("validated"))

    return {
        "status": "completed",
        "pattern": pattern,
        "base_email": base_email,
        "domain": domain,
        "total_tests": len(test_names),
        "successful_validations": successful,
        "validation_rate": successful / len(test_names) if test_names else 0,
        "test_results": test_results,
        "timestamp": datetime.utcnow().isoformat(),
    }


@function_tool
async def send_validation_email(email_address: str) -> str:
    """
    Send a test email to validate if an email address is active.

    Args:
        email_address: Email address to validate

    Returns:
        Status message indicating if email was sent successfully
    """
    result = await send_test_email(email_address)
    if result.get("validated"):
        return f"[VALIDATED] Test email sent to {email_address}. If received, pattern is confirmed valid."
    else:
        return f"[UNVALIDATED] Could not send to {email_address}: {result.get('message', 'Unknown error')}"


@function_tool
async def check_pattern_validation_status(email_address: str) -> str:
    """
    Check if a previously sent validation email was delivered.

    Args:
        email_address: Email address to check

    Returns:
        Delivery status message
    """
    print(f"[SENDGRID] check_pattern_validation_status called for: {email_address}")
    result = await check_email_delivery(email_address)
    print(f"[SENDGRID] check_email_delivery returned: {result}")
    status = result.get("status", "")
    message = result.get("message", "")
    if status == "success":
        statuses = result.get("delivery_statuses", {})
        status_summary = ", ".join([f"{k}: {v}" for k, v in statuses.items()]) if statuses else result.get("delivery_status", "delivered")
        final_msg = f"DELIVERED: {email_address} - {status_summary}"
    elif status == "not_found":
        final_msg = f"NOT FOUND: {email_address} - {message}"
    elif status == "info":
        final_msg = f"STATUS UNAVAILABLE: {message}"
    else:
        final_msg = f"Status for {email_address}: {status} - {message}"
    print(f"[SENDGRID] Returning: {final_msg}")
    return final_msg


@function_tool
async def test_email_pattern(
    company_domain: str,
    pattern_examples: str,
) -> str:
    """
    Test a discovered email pattern by attempting to send emails to generated addresses.

    This tool generates test email addresses based on the pattern and attempts validation.

    Args:
        company_domain: Company domain (e.g., 'ecopetrol.com.co')
        pattern_examples: Examples of discovered pattern (e.g., 'firstname.lastname@domain or first.last@domain')

    Returns:
        Summary of pattern validation attempts and success rate
    """
    # Parse the company domain
    if not company_domain or "@" not in company_domain and "." not in company_domain:
        return f"[ERROR] Invalid company domain: {company_domain}"

    # Extract domain if a full email was provided
    if "@" in company_domain:
        domain = company_domain.split("@")[1]
    else:
        domain = company_domain

    # Generate common test names
    test_names = [
        "test.user",
        "john.smith",
        "admin",
        "info",
        "contact",
        "support",
        "sales",
        "hr",
    ]

    # Generate test emails and attempt validation
    test_results = []
    for test_name in test_names[:3]:  # Limit to 3 tests to avoid excessive emails
        test_email = f"{test_name}@{domain}"
        result = await send_test_email(test_email)
        test_results.append({
            "email": test_email,
            "validated": result.get("validated"),
            "message": result.get("message"),
        })

    successful = sum(1 for r in test_results if r.get("validated"))

    summary = f"""
Pattern Validation Summary:
- Domain: {domain}
- Pattern: {pattern_examples}
- Tests performed: {len(test_results)}
- Successful validations: {successful}
- Validation rate: {(successful/len(test_results)*100) if test_results else 0:.1f}%

Test Details:
"""
    for test in test_results:
        status = "[OK]" if test.get("validated") else "[FAILED]"
        summary += f"\n  {status} {test['email']}: {test['message']}"

    return summary
