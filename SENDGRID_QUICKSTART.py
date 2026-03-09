#!/usr/bin/env python3
"""
SENDGRID EMAIL VALIDATION - QUICK START GUIDE
==============================================

What: System can now send test emails to validate discovered email patterns
When: During research, agent uses SendGrid to verify patterns
Why: Confirms that patterns work with real email addresses
How: Automatic - just configure SendGrid API key

## 5-Minute Setup

1. Create SendGrid account:
   https://sendgrid.com (sign up free)

2. Get API key:
   https://app.sendgrid.com/settings/api_keys

3. Verify sender email:
   https://app.sendgrid.com/settings/sender_auth

4. Add to .env:
   SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxx

5. Test:
   python test_sendgrid.py

## How It Works

Research Task: "Find email pattern for Ecopetrol"
    ↓
Agent searches web
    ↓
Discovers: "firstname.lastname@ecopetrol.com.co"
    ↓
Agent uses SendGrid to send test emails:
    maria.garcia@ecopetrol.com.co
    carlos.lopez@ecopetrol.com.co
    ana.martinez@ecopetrol.com.co
    ↓
Receives delivery status for each
    ↓
Reports: "Pattern validated! 2/3 deliveries successful"
    ↓
Research output includes validation status

## Tools Available to Agents

1. send_validation_email(email_address)
   → Sends test email to single address
   → Returns: [VALIDATED] or [UNVALIDATED] with reason

2. check_pattern_validation_status(email_address)
   → Checks delivery status
   → Returns: Delivery status (sent/delivered/bounced/etc)

3. test_email_pattern(domain, pattern)
   → Tests discovered pattern with multiple addresses
   → Returns: Success rate and individual test results

## SendGrid Quotas

Free tier: 30 emails/day
Paid tier: Starting at $29.95/month

For testing/small research: Free tier is enough

## Important Notes

- Emails are clearly marked as test/validation emails
- No misleading content - recipients know it's a test
- Takes 2-5 seconds for SendGrid to show delivery status
- Check SendGrid dashboard to see detailed delivery events

## Monitoring

SendGrid Dashboard: https://app.sendgrid.com
Check "Mail Activity" to see:
  - Email sent/delivered/bounced
  - When recipient opened email
  - All delivery events

## Integration with Research

When running email pattern research:

python run_email_pattern_research.py "Ecopetrol"

If SENDGRID_API_KEY is configured:
  ✓ Agent will automatically validate patterns
  ✓ Research output will include validation status
  ✓ You'll see which patterns are confirmed valid

If SENDGRID_API_KEY is NOT configured:
  ✓ Research still works normally
  ✓ Patterns discovered but not validated
  ✓ Add API key anytime to enable validation

## Example Output

Before SendGrid:
  "Email pattern appears to be: firstname.lastname@company.com"

After SendGrid:
  "Email pattern: firstname.lastname@company.com
   Validation: 2/3 successful tests
   Status: CONFIRMED VALID"

## Troubleshooting

SendGrid HTTP 401: Unauthorized
  → Check API key is correct in .env

SendGrid HTTP 403: Forbidden
  → Verify sender email in SendGrid dashboard

No messages found
  → Emails sent successfully but status not yet available
  → Check SendGrid dashboard (Mail Activity tab)

Invalid email format
  → Email address malformed (missing @ or domain)

## Files Created/Modified

NEW:
  - deep_researcher/tools/sendgrid_tools.py (core integration)
  - test_sendgrid.py (test script)
  - SENDGRID_INTEGRATION.md (full documentation)
  - SENDGRID_SUMMARY.md (this file)

MODIFIED:
  - search_agent.py (added SendGrid tools to agent)
  - .env.example (added SendGrid configuration)

## Test Commands

# Test SendGrid setup
python test_sendgrid.py

# Run research with email pattern discovery
python run_email_pattern_research.py "Ecopetrol"

# Run with custom domain hint
python run_email_pattern_research.py "Ecopetrol" --domain ecopetrol.com.co

## Example Workflow

1. Setup SendGrid (5 minutes)
2. Run research: python run_email_pattern_research.py "YourCompany"
3. Agent discovers patterns
4. Agent sends test emails to validate
5. Check SendGrid dashboard for delivery status
6. Review research report with validation results

## Optional: Customize Sender

By default, emails come from: noreply@deepresearch.dev

To customize, add to .env:
  SENDGRID_SENDER_EMAIL=your-email@yourcompany.com

Must be verified in SendGrid dashboard first!

## Cost

Free tier: $0 (30 emails/day)
Paid tier: $29.95/month (100k emails)

For single research run with pattern validation:
  - Typical cost: $0 (free tier)
  - Max emails per company: ~10-20
  - With 30 daily limit: Can validate 2-3 patterns/day

## Next Step

Ready? Run:
  python test_sendgrid.py

Then run your research:
  python run_email_pattern_research.py "Ecopetrol"
"""

if __name__ == "__main__":
    import sys
    print(__doc__)
