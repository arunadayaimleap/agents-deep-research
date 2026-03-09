#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

print("SendGrid Diagnostic")
print("=" * 60)
print()

if not SENDGRID_API_KEY:
    print("[ERROR] SENDGRID_API_KEY not found in .env")
else:
    print(f"API Key found: {SENDGRID_API_KEY[:30]}...")
    print(f"Key length: {len(SENDGRID_API_KEY)}")
    print(f"Key starts with 'SG.': {SENDGRID_API_KEY.startswith('SG.')}")
    print()
    
    # Show what the header will look like
    header = f"Bearer {SENDGRID_API_KEY}"
    print(f"Authorization header will be:")
    print(f"  {header[:50]}...")
    print()
    
    # Check for common issues
    if " " in SENDGRID_API_KEY:
        print("[WARNING] API key contains spaces - this will cause 401 error")
    if SENDGRID_API_KEY.startswith(" ") or SENDGRID_API_KEY.endswith(" "):
        print("[WARNING] API key has leading/trailing spaces - will cause 401 error")
    if not SENDGRID_API_KEY.startswith("SG."):
        print("[WARNING] API key doesn't start with 'SG.' - might be incorrect format")
    
    print()
    print("Test with curl:")
    print(f'curl -X POST https://api.sendgrid.com/v3/mail/send \\')
    print(f'  -H "Authorization: Bearer {SENDGRID_API_KEY[:30]}..." \\')
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"personalizations": [{{"to": [{{"email": "test@example.com"}}]}}], "from": {{"email": "orusdata8@gmail.com"}}, "subject": "Test", "content": [{{"type": "text/plain", "value": "Test"}}]}}\'')
