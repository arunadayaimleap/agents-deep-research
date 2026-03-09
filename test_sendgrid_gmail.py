"""Test SendGrid: send to arunadaybasu@gmail.com, wait 60 sec, check status."""
import asyncio
from deep_researcher.tools.sendgrid_tools import send_test_email, check_email_delivery


async def main():
    email = "arunadaybasu@gmail.com"
    print(f"\n1. Sending test email to {email}...")
    send_result = await send_test_email(email)
    print(f"   Send result: {send_result.get('status')} - {send_result.get('message')}")

    print(f"\n2. Waiting 60 seconds for delivery...")
    await asyncio.sleep(60)

    print(f"\n3. Checking delivery status for {email}...")
    status_result = await check_email_delivery(email, hours_back=1)
    print(f"   Status result: {status_result}")


if __name__ == "__main__":
    asyncio.run(main())
