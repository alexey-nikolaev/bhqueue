"""
First-time Telegram authentication setup.

Run this script ONCE to authenticate with Telegram and create a session file.
After running this, the backend will auto-connect using the saved session.

Usage:
    python -m scripts.setup_telegram
"""

import asyncio
from telethon import TelegramClient
from app.config import get_settings

settings = get_settings()


async def main():
    print("=" * 50)
    print("Telegram Authentication Setup")
    print("=" * 50)
    print()
    
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("ERROR: Telegram credentials not configured in .env")
        print("Get them from https://my.telegram.org")
        return
    
    print(f"API ID: {settings.telegram_api_id}")
    print(f"Phone: {settings.telegram_phone or 'Not set (will prompt)'}")
    print()
    print("This will send a verification code to your Telegram app.")
    print("Press Enter to continue or Ctrl+C to cancel...")
    input()
    
    try:
        api_id = int(settings.telegram_api_id)
    except ValueError:
        print("ERROR: Invalid TELEGRAM_API_ID")
        return
    
    # Create client with same session name as the monitor uses
    client = TelegramClient(
        "bhqueue_session",  # Must match TelegramMonitor.session_name
        api_id,
        settings.telegram_api_hash,
    )
    
    print("\nConnecting to Telegram...")
    await client.start(phone=settings.telegram_phone)
    
    # Verify connection
    me = await client.get_me()
    print()
    print("=" * 50)
    print(f"SUCCESS! Authenticated as: {me.first_name} (@{me.username})")
    print("=" * 50)
    print()
    print("Session saved to: bhqueue_session.session")
    print("The backend will now auto-connect when started.")
    print()
    
    # Test access to the Berghain group
    print("Testing access to @berghainberlin group...")
    try:
        entity = await client.get_entity("berghainberlin")
        print(f"✓ Found group: {entity.title}")
        
        # Get a sample message
        async for msg in client.iter_messages(entity, limit=1):
            if msg.text:
                preview = msg.text[:100] + "..." if len(msg.text) > 100 else msg.text
                print(f"✓ Latest message: {preview}")
                break
    except Exception as e:
        print(f"✗ Could not access group: {e}")
        print("  Make sure you've joined @berghainberlin on Telegram")
    
    await client.disconnect()
    print("\nSetup complete! You can now start the backend.")


if __name__ == "__main__":
    asyncio.run(main())
