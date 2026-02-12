"""
Fetch Telegram messages from last Klubnacht.

Run with: python -m scripts.fetch_klubnacht_messages
"""

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telethon import TelegramClient
from app.config import get_settings

settings = get_settings()

# Berlin timezone
BERLIN_TZ = ZoneInfo("Europe/Berlin")

# Klubnacht time range (last Saturday 21:00 to Monday 08:00 Berlin time)
# Today is Thursday Feb 12, 2026, so last Saturday was Feb 7, 2026
START_TIME = datetime(2026, 2, 7, 21, 0, 0, tzinfo=BERLIN_TZ)  # Saturday 21:00
END_TIME = datetime(2026, 2, 9, 8, 0, 0, tzinfo=BERLIN_TZ)     # Monday 08:00

BERGHAIN_GROUP = "berghainberlin"
OUTPUT_FILE = "klubnacht_messages_2026-02-07.txt"


async def main():
    print("=" * 60)
    print("Fetching Telegram messages from last Klubnacht")
    print("=" * 60)
    print(f"Time range: {START_TIME.strftime('%Y-%m-%d %H:%M %Z')} to {END_TIME.strftime('%Y-%m-%d %H:%M %Z')}")
    print()
    
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("ERROR: Telegram credentials not configured")
        return
    
    try:
        api_id = int(settings.telegram_api_id)
    except ValueError:
        print("ERROR: Invalid TELEGRAM_API_ID")
        return
    
    client = TelegramClient(
        "bhqueue_session",
        api_id,
        settings.telegram_api_hash,
    )
    
    print("Connecting to Telegram...")
    await client.start(phone=settings.telegram_phone)
    print("Connected!")
    print()
    
    print(f"Fetching messages from @{BERGHAIN_GROUP}...")
    
    messages = []
    count = 0
    
    # Fetch messages - Telethon returns newest first, so we use offset_date for end time
    # and filter by date for start time
    async for message in client.iter_messages(
        BERGHAIN_GROUP,
        offset_date=END_TIME,  # Start from end time (newest we want)
        reverse=False,  # Go backwards in time
    ):
        # Convert message date to Berlin time for comparison
        msg_time_utc = message.date.replace(tzinfo=timezone.utc)
        msg_time_berlin = msg_time_utc.astimezone(BERLIN_TZ)
        
        # Stop if we've gone past the start time
        if msg_time_berlin < START_TIME:
            break
        
        # Skip messages after end time (shouldn't happen with offset_date, but just in case)
        if msg_time_berlin > END_TIME:
            continue
        
        count += 1
        if count % 50 == 0:
            print(f"  Fetched {count} messages...")
        
        # Get message text or media type
        if message.text:
            content = message.text
        elif message.photo:
            content = "[Photo]"
        elif message.video:
            content = "[Video]"
        elif message.document:
            content = "[Document/File]"
        elif message.sticker:
            content = "[Sticker]"
        else:
            content = "[Media]"
        
        # Get sender info
        sender_name = "Unknown"
        if message.sender:
            if hasattr(message.sender, 'first_name'):
                sender_name = message.sender.first_name or ""
                if hasattr(message.sender, 'last_name') and message.sender.last_name:
                    sender_name += f" {message.sender.last_name}"
            elif hasattr(message.sender, 'title'):
                sender_name = message.sender.title
        
        messages.append({
            "id": message.id,
            "time": msg_time_berlin,
            "sender": sender_name.strip(),
            "content": content,
            "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None,
        })
    
    print(f"\nTotal messages fetched: {len(messages)}")
    
    # Sort by time (oldest first)
    messages.sort(key=lambda m: m["time"])
    
    # Write to file
    print(f"\nWriting to {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("BERGHAIN TELEGRAM GROUP - KLUBNACHT MESSAGES\n")
        f.write(f"Time range: {START_TIME.strftime('%Y-%m-%d %H:%M')} to {END_TIME.strftime('%Y-%m-%d %H:%M')} Berlin time\n")
        f.write(f"Total messages: {len(messages)}\n")
        f.write("=" * 70 + "\n\n")
        
        current_date = None
        for msg in messages:
            # Add date header when day changes
            msg_date = msg["time"].strftime("%A, %B %d, %Y")
            if msg_date != current_date:
                current_date = msg_date
                f.write(f"\n{'─' * 50}\n")
                f.write(f"  {msg_date}\n")
                f.write(f"{'─' * 50}\n\n")
            
            time_str = msg["time"].strftime("%H:%M")
            reply_str = f" [reply to #{msg['reply_to']}]" if msg["reply_to"] else ""
            
            f.write(f"[{time_str}] {msg['sender']}{reply_str}:\n")
            # Indent multi-line messages
            for line in msg["content"].split("\n"):
                f.write(f"    {line}\n")
            f.write("\n")
    
    print(f"Done! Saved {len(messages)} messages to {OUTPUT_FILE}")
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
