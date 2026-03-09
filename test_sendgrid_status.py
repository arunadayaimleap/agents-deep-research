"""Quick test of SendGrid delivery status check."""
import asyncio
from deep_researcher.tools.sendgrid_tools import check_email_delivery


async def main():
    # Test with real email that was just sent
    result = await check_email_delivery("arunaday.b@aimleap.com", hours_back=1)
    print("\nResult:", result)


if __name__ == "__main__":
    asyncio.run(main())
