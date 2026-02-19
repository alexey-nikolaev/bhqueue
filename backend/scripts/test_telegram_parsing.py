"""
Test Telegram parsing with messages from a specific time.

Fetches messages from around 03:00 Berlin time on Sunday Feb 8, 2026,
parses them, shows interpretation, and inserts into database.

Run with: python -m scripts.test_telegram_parsing
"""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telethon import TelegramClient
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_maker
from app.models import Club, ParsedUpdate, Event
from app.services.queue_parser import parse_queue_message
from app.services.ai_queue_parser import parse_with_ai

settings = get_settings()

# Berlin timezone
BERLIN_TZ = ZoneInfo("Europe/Berlin")

# Target time: Sunday Feb 8, 2026 at 03:00 Berlin time
# Fetch messages from last 2 hours (01:00 to 03:00) - only messages available at that time
TARGET_TIME = datetime(2026, 2, 8, 3, 0, 0, tzinfo=BERLIN_TZ)
START_TIME = datetime(2026, 2, 8, 1, 0, 0, tzinfo=BERLIN_TZ)  # 2 hours before
END_TIME = datetime(2026, 2, 8, 3, 0, 0, tzinfo=BERLIN_TZ)    # Up to 03:00

# The app only uses messages from last 30 minutes for queue estimate
ESTIMATE_WINDOW_START = datetime(2026, 2, 8, 2, 30, 0, tzinfo=BERLIN_TZ)  # 02:30

BERGHAIN_GROUP = "berghainberlin"


async def main():
    print("=" * 70)
    print("TELEGRAM PARSING TEST - Sunday Feb 8, 2026 at 03:00")
    print("=" * 70)
    print(f"Simulating: What would the app show at 03:00?")
    print(f"Fetching messages from {START_TIME.strftime('%H:%M')} to {END_TIME.strftime('%H:%M')} Berlin time")
    print()
    
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("ERROR: Telegram credentials not configured")
        return
    
    try:
        api_id = int(settings.telegram_api_id)
    except ValueError:
        print("ERROR: Invalid TELEGRAM_API_ID")
        return
    
    # Connect to Telegram
    client = TelegramClient(
        "bhqueue_session",
        api_id,
        settings.telegram_api_hash,
    )
    
    print("Connecting to Telegram...")
    await client.start(phone=settings.telegram_phone)
    print("Connected!\n")
    
    # Fetch messages
    print(f"Fetching messages from @{BERGHAIN_GROUP}...")
    
    messages = []
    async for message in client.iter_messages(
        BERGHAIN_GROUP,
        offset_date=END_TIME,
        reverse=False,
    ):
        msg_time_utc = message.date.replace(tzinfo=timezone.utc)
        msg_time_berlin = msg_time_utc.astimezone(BERLIN_TZ)
        
        if msg_time_berlin < START_TIME:
            break
        if msg_time_berlin > END_TIME:
            continue
        
        if message.text:
            sender_name = "Unknown"
            if message.sender:
                if hasattr(message.sender, 'first_name'):
                    sender_name = message.sender.first_name or ""
                    if hasattr(message.sender, 'last_name') and message.sender.last_name:
                        sender_name += f" {message.sender.last_name}"
            
            messages.append({
                "id": message.id,
                "time": msg_time_berlin,
                "sender": sender_name.strip(),
                "content": message.text,
            })
    
    await client.disconnect()
    
    # Sort oldest first
    messages.sort(key=lambda m: m["time"])
    
    print(f"Found {len(messages)} text messages\n")
    
    # Filter to messages in the 30-min window
    window_messages = [m for m in messages if m["time"] >= ESTIMATE_WINDOW_START]
    
    print("=" * 70)
    print("MESSAGES IN 30-MIN WINDOW (02:30-03:00)")
    print("=" * 70)
    
    if not window_messages:
        print("No messages in the 30-min window.")
        return
    
    for msg in window_messages:
        print(f"\n[{msg['time'].strftime('%H:%M')}] {msg['sender']}:")
        print(f"    {msg['content'][:100]}{'...' if len(msg['content']) > 100 else ''}")
    
    # Use AI to summarize all messages at once
    print(f"\n\n{'=' * 70}")
    print("AI SUMMARY (analyzing all messages together)")
    print("=" * 70)
    
    use_ai = settings.anthropic_api_key and settings.enable_ai_parsing
    
    if not use_ai:
        print("⚠ AI parsing disabled - set ANTHROPIC_API_KEY in .env")
        return
    
    # Build message list for AI
    messages_text = "\n".join([
        f"[{msg['time'].strftime('%H:%M')}] {msg['sender']}: {msg['content']}"
        for msg in window_messages
    ])
    
    # Call AI for summary
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    
    summary_prompt = f"""Analyze these Telegram messages from the Berghain queue group and provide a queue status summary.

MESSAGES (from the last 30 minutes):
{messages_text}

Based on these messages, provide:
1. Current queue length estimate (none/short/medium/long/very_long)
2. Estimated wait time in minutes
3. Any spatial marker mentioned (Snake, Kiosk, etc.)
4. Rejection rate if mentioned (low/medium/high)
5. Brief reasoning

Respond in JSON format:
{{
    "queue_length": "none" | "short" | "medium" | "long" | "very_long",
    "wait_minutes": <number>,
    "spatial_marker": "<marker or null>",
    "rejection_rate": "<rate or null>",
    "confidence": <0.0-1.0>,
    "reasoning": "<brief explanation>"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": summary_prompt}]
        )
        
        response_text = response.content[0].text.strip()
        
        # Handle markdown code blocks
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        import json
        summary = json.loads(response_text)
        
        print(f"\n✓ AI Analysis Complete:")
        print(f"    → Queue length: {summary.get('queue_length', '-')}")
        print(f"    → Wait time: {summary.get('wait_minutes', '-')} min")
        print(f"    → Spatial marker: {summary.get('spatial_marker', '-')}")
        print(f"    → Rejection rate: {summary.get('rejection_rate', '-')}")
        print(f"    → Confidence: {summary.get('confidence', 0):.0%}")
        print(f"\n    Reasoning: {summary.get('reasoning', '-')}")
        
        # Store for database insertion
        parsed_messages = [{
            "summary": True,
            "parsed": type('Summary', (), {
                'queue_length': summary.get('queue_length'),
                'wait_minutes': summary.get('wait_minutes'),
                'spatial_marker': summary.get('spatial_marker'),
                'rejection_rate': summary.get('rejection_rate'),
                'confidence': summary.get('confidence', 0.8),
            })(),
        }]
        messages_in_window = [parsed_messages[0]["parsed"]]
        
    except Exception as e:
        print(f"\n✗ AI Error: {e}")
        return
    
    # Show what the app would display
    print(f"\n\n{'=' * 70}")
    print("APP WOULD SHOW")
    print("=" * 70)
    
    if messages_in_window:
        parsed = messages_in_window[0]
        wait = getattr(parsed, 'wait_minutes', None)
        marker = getattr(parsed, 'spatial_marker', None)
        
        if wait is not None:
            print(f"    Estimated wait: ~{wait} min")
        else:
            print(f"    Estimated wait: No data")
        if marker:
            print(f"    Queue at: {marker}")
    
    print("=" * 70)
    
    # Ask to insert into database
    print(f"\nDo you want to insert this summary into the database? (y/n): ", end="", flush=True)
    user_response = input().strip().lower()
    
    if user_response != 'y':
        print("Skipped database insertion.")
        return
    
    # Insert into database
    print("\nInserting into database with CURRENT timestamps (so they show in app)...")
    
    async with async_session_maker() as db:
        # Get Berghain club
        result = await db.execute(select(Club).where(Club.slug == "berghain"))
        club = result.scalar_one_or_none()
        
        if not club:
            print("ERROR: Berghain club not found in database")
            return
        
        # Get or create event for this time
        result = await db.execute(
            select(Event)
            .where(Event.club_id == club.id)
            .order_by(Event.starts_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        
        # Use current time for timestamp so data shows in app
        now = datetime.utcnow()
        
        # Get the summary data
        parsed = messages_in_window[0]
        
        # Create a single ParsedUpdate with the AI summary
        update = ParsedUpdate(
            club_id=club.id,
            event_id=event.id if event else None,
            source="telegram_ai_summary",
            source_id=f"ai-summary-{now.timestamp()}",
            author_name="AI Summary",
            raw_text=f"AI analysis of {len(window_messages)} messages from 02:30-03:00",
            parsed_wait_minutes=getattr(parsed, 'wait_minutes', None),
            parsed_queue_length=getattr(parsed, 'queue_length', None),
            parsed_spatial_marker=getattr(parsed, 'spatial_marker', None),
            confidence=getattr(parsed, 'confidence', 0.8),
            source_timestamp=now,
        )
        db.add(update)
        
        await db.commit()
        print(f"Inserted AI summary into database.")
    
    print("\nDone! The queue estimate should now show in the app.")
    print("Note: The app shows data from the last 30 minutes by default.")
    print("You may need to adjust the backend to use historical data for testing.")


if __name__ == "__main__":
    asyncio.run(main())
