# SendGrid Email Pattern Validation Integration

## Overview

SendGrid tools enable the research system to validate discovered email patterns by:
1. **Sending test emails** to discovered email addresses
2. **Checking delivery status** to confirm if addresses are active
3. **Validating patterns** by testing multiple variations
4. **Reporting validation results** in the research output

## Features

### 1. Send Validation Email
**Purpose**: Test if a specific email address exists and accepts mail

```python
from deep_researcher.tools.sendgrid_tools import send_test_email

result = await send_test_email("john.doe@company.com")
# Returns: {"status": "success", "validated": True, ...}
```

**Returns**:
- `status`: "success" or "error"
- `validated`: Boolean indicating if email was sent
- `message`: Description of result
- `timestamp`: When email was sent

### 2. Check Email Delivery Status
**Purpose**: Track delivery status of sent emails

```python
from deep_researcher.tools.sendgrid_tools import check_email_delivery

result = await check_email_delivery("john.doe@company.com", hours_back=24)
# Returns delivery events (sent, delivered, bounced, opened, clicked)
```

**Returns**:
- `status`: "success", "not_found", or "error"
- `delivery_statuses`: Summary of delivery events
- `message_count`: Number of messages found
- `latest_event`: Most recent delivery event

### 3. Validate Email Pattern
**Purpose**: Test an entire email pattern with multiple variations

```python
from deep_researcher.tools.sendgrid_tools import validate_email_pattern

result = await validate_email_pattern(
    base_email="john.doe@company.com",
    pattern="firstname.lastname@company.com",
    test_names=["jane.smith", "bob.jones", "alice.brown"],
    company_domain="company.com"
)
# Tests: jane.smith@company.com, bob.jones@company.com, alice.brown@company.com
```

**Returns**:
- `pattern`: The tested pattern
- `total_tests`: Number of tests performed
- `successful_validations`: How many succeeded
- `validation_rate`: Success percentage
- `test_results`: Individual results for each test

## Function Tools (Agent Usage)

### 1. `send_validation_email(email_address: str) -> str`
Agent tool to send a test email to an address.

**Usage in agents**:
```
send_validation_email("contact@company.com")
# Returns: "[VALIDATED] Test email sent to contact@company.com."
```

### 2. `check_pattern_validation_status(email_address: str) -> str`
Agent tool to check delivery status of a validation email.

**Usage in agents**:
```
check_pattern_validation_status("contact@company.com")
# Returns: "Delivery status for contact@company.com: delivered: 1, opened: 1"
```

### 3. `test_email_pattern(company_domain: str, pattern_examples: str) -> str`
Agent tool to validate a discovered email pattern with test emails.

**Usage in agents**:
```
test_email_pattern(
    "company.com",
    "firstname.lastname@domain or first.last@domain"
)
# Returns summary of validation attempts
```

## Integration with Agents

### WebSearchAgent Enhancement
The WebSearchAgent now includes SendGrid tools and instructions to:

1. **Discover email patterns** during web search
2. **Validate patterns** by sending test emails
3. **Report validation status** in the summary

**Updated instructions**:
```
If your research discovers potential email addresses or email patterns:
- Use send_validation_email to test if the address is active
- Use test_email_pattern to validate a discovered pattern with multiple test addresses
- Use check_pattern_validation_status to verify delivery status of test emails
- Report which patterns were successfully validated
```

### Research Workflow
```
User Query: "Find email pattern for Ecopetrol"
    ↓
WebSearchAgent
    ↓ (searches for email patterns)
Discovers: "firstname.lastname@ecopetrol.com.co"
    ↓
Uses send_validation_email() to test variations
    ↓
Receives validation results (success/bounce/timeout)
    ↓
Reports: "Pattern 'firstname.lastname@ecopetrol.com.co' validated with 3/5 successful tests"
    ↓
Stores results in research output
```

## Configuration

### Setup SendGrid Account
1. Go to [SendGrid.com](https://sendgrid.com)
2. Create free account (30 emails/day limit free tier)
3. Create API key at: https://app.sendgrid.com/settings/api_keys
4. Set verified sender email at: https://app.sendgrid.com/settings/sender_auth

### .env Configuration
```env
# Required for email validation
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxx

# Optional (defaults to noreply@deepresearch.dev)
SENDGRID_SENDER_EMAIL=your-verified-sender@company.com
```

### Environment Setup Checklist
- [ ] SendGrid account created
- [ ] API key generated
- [ ] Sender email verified in SendGrid dashboard
- [ ] Added `SENDGRID_API_KEY` to `.env`
- [ ] (Optional) Added `SENDGRID_SENDER_EMAIL` to `.env`

## Usage Examples

### Example 1: Test a Single Email Address
```python
from deep_researcher.tools.sendgrid_tools import send_test_email

# Send test email
result = await send_test_email("john.doe@ecopetrol.com.co")

if result['validated']:
    print("Email address is valid and accepting mail!")
else:
    print("Email did not accept the test:", result['message'])
```

### Example 2: Validate an Email Pattern
```python
from deep_researcher.tools.sendgrid_tools import validate_email_pattern

# Test pattern with multiple names
result = await validate_email_pattern(
    base_email="john.doe@ecopetrol.com.co",
    pattern="firstname.lastname@ecopetrol.com.co",
    test_names=["maria.lopez", "carlos.gomez", "ana.rodriguez"],
)

print(f"Pattern validation success rate: {result['validation_rate']*100:.1f}%")
print(f"Tested: {result['total_tests']} addresses")
print(f"Successful: {result['successful_validations']} validations")
```

### Example 3: Research with Pattern Validation
```bash
python run_email_pattern_research.py "Ecopetrol" --sendgrid-validate
```

During research:
- Agent discovers email patterns
- Automatically sends test emails
- Reports which patterns are confirmed active
- Shows validation success rate

## Email Limits and Quotas

### SendGrid Free Tier
- **Limit**: 30 emails/day (free account)
- **Cost**: Free for up to 100 contacts/month
- **Use**: Great for testing and small-scale validation

### SendGrid Paid Plans
- **Basic**: $29.95/month for 100k emails
- **Higher tiers**: Available for large-scale research

### Recommendations
1. **For small research**: Use free tier (30/day)
2. **For regular validation**: Upgrade to paid plan
3. **For limited budget**: Validate only critical patterns

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `SENDGRID_API_KEY not configured` | Missing API key in .env | Add `SENDGRID_API_KEY` to .env |
| `Invalid email format` | Malformed email address | Ensure email has @ and domain |
| `SendGrid HTTP 401: Unauthorized` | Invalid API key | Check key in SendGrid dashboard |
| `SendGrid HTTP 403: Forbidden` | Sender email not verified | Verify sender in SendGrid dashboard |
| `Request timeout (30 seconds)` | Network issue | Check internet connection |
| `No messages found` | No delivery history | Emails may not have been sent yet |

## Monitoring and Analytics

### SendGrid Dashboard
Monitor all validation emails at: https://app.sendgrid.com/email_activity

**Metrics tracked**:
- **Sent**: Email successfully queued
- **Delivered**: Email reached recipient inbox
- **Bounced**: Email rejected (permanent or temporary)
- **Opened**: Recipient opened the email
- **Clicked**: Recipient clicked a link (if applicable)

### Interpreting Results

**Pattern Validation Rate**:
```
Success Rate = Delivered / Total Sent * 100%

- 80-100%: Pattern is very likely correct
- 60-80%: Pattern is probably correct (some invalid addresses)
- 40-60%: Pattern may be partially correct
- 0-40%: Pattern is likely incorrect
```

## Best Practices

1. **Start small**: Test 3-5 variations before full validation
2. **Use real names**: Test with actual employee names if possible
3. **Check results carefully**: Review SendGrid dashboard for delivery events
4. **Space out tests**: Add delays between emails to avoid rate limiting
5. **Document patterns**: Record which patterns succeeded for future reference

## Testing

### Test SendGrid Configuration
```bash
python test_sendgrid.py
```

Expected output:
```
SendGrid Configuration:
  API Key: SG.xxxxxxxxxxxxxxxxxx...
  Sender Email: noreply@deepresearch.dev

[Test 1] Sending test email to validate basic functionality...
  Recipient: test@example.com
  Status: success
  Message: Test email sent to test@example.com
  Validated: True

[Test 2] Checking delivery status...
  Email: test@example.com
  Status: not_found
  Message: No messages found for test@example.com in last 1 hours

[Test 3] Validating email pattern...
  Pattern: firstname.lastname@company.com
  Domain: company.com
  Total Tests: 3
  Successful: 0
  Validation Rate: 0.0%
```

## Integration with Research Pipeline

### Modified Files

1. **search_agent.py**
   - Added SendGrid tool imports
   - Updated instructions with email validation guidance
   - Conditionally adds SendGrid tools if API key exists

2. **sendgrid_tools.py** (new)
   - Core functions for email sending and validation
   - Function tools for agent use
   - Error handling and retry logic

3. **test_sendgrid.py** (new)
   - Integration test for SendGrid tools
   - Demonstrates all three validation methods

4. **.env.example**
   - Added SENDGRID_API_KEY and SENDGRID_SENDER_EMAIL

## Future Enhancements

Potential improvements for email validation:
- [ ] Email verification API integration (Verifalia, Bouncer)
- [ ] Pattern learning from successful emails
- [ ] Automatic retry logic for temporary failures
- [ ] Machine learning for pattern prediction
- [ ] Integration with company databases (LinkedIn, RocketReach)
- [ ] A/B testing different patterns

## Support and Troubleshooting

### SendGrid Documentation
- [SendGrid API Reference](https://docs.sendgrid.com/api-reference)
- [Email Activity](https://docs.sendgrid.com/for-developers/tracking-events/event-webhook)
- [API Keys](https://docs.sendgrid.com/ui/account-and-settings/api-keys)

### Common Questions

**Q: Can I use a free SendGrid account?**
A: Yes, free account allows 30 emails/day. Upgrade to paid plan for higher limits.

**Q: Will the recipient know it's a test email?**
A: Yes, the email clearly states it's a test from "Deep Research Email Pattern Validation system".

**Q: How long does delivery take?**
A: Usually 2-5 seconds for delivery confirmation.

**Q: Can I validate without SendGrid?**
A: Yes, but email validation requires SendGrid. Without it, patterns are discovered but not validated.

**Q: What if the company blocks external emails?**
A: Bounced emails will show as "bounce" status in SendGrid, indicating the domain/pattern is incorrect.
