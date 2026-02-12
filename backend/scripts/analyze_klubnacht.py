"""
Analyze Klubnacht messages using AI.

Run with: python -m scripts.analyze_klubnacht
"""

import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from telethon import TelegramClient
from app.config import get_settings
from app.services.ai_queue_parser import parse_with_ai, analyze_klubnacht_messages

settings = get_settings()

BERLIN_TZ = ZoneInfo("Europe/Berlin")

# Last Klubnacht: Saturday Feb 7 21:00 to Monday Feb 9 08:00
START_TIME = datetime(2026, 2, 7, 21, 0, 0, tzinfo=BERLIN_TZ)
END_TIME = datetime(2026, 2, 9, 8, 0, 0, tzinfo=BERLIN_TZ)

BERGHAIN_GROUP = "berghainberlin"


async def main():
    print("=" * 60)
    print("AI-Powered Klubnacht Message Analysis")
    print("=" * 60)
    
    if not settings.anthropic_api_key:
        print("\nERROR: ANTHROPIC_API_KEY not set in .env")
        print("Get your API key from: https://console.anthropic.com")
        return
    
    print(f"\nTime range: {START_TIME.strftime('%Y-%m-%d %H:%M')} to {END_TIME.strftime('%Y-%m-%d %H:%M')} Berlin time")
    
    # Connect to Telegram
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("ERROR: Telegram credentials not configured")
        return
    
    client = TelegramClient(
        "bhqueue_session",
        int(settings.telegram_api_id),
        settings.telegram_api_hash,
    )
    
    print("\nConnecting to Telegram...")
    await client.start(phone=settings.telegram_phone)
    print("Connected!")
    
    # Fetch messages
    print(f"\nFetching messages from @{BERGHAIN_GROUP}...")
    
    messages = []
    async for message in client.iter_messages(
        BERGHAIN_GROUP,
        offset_date=END_TIME,
        reverse=False,
    ):
        from datetime import timezone
        msg_time_utc = message.date.replace(tzinfo=timezone.utc)
        msg_time_berlin = msg_time_utc.astimezone(BERLIN_TZ)
        
        if msg_time_berlin < START_TIME:
            break
        if msg_time_berlin > END_TIME:
            continue
        
        if not message.text:
            continue
        
        sender_name = "Unknown"
        if message.sender:
            if hasattr(message.sender, 'first_name'):
                sender_name = message.sender.first_name or ""
            elif hasattr(message.sender, 'title'):
                sender_name = message.sender.title
        
        messages.append({
            "text": message.text,
            "content": message.text,  # Alias for analyze function
            "time": msg_time_berlin,
            "timestamp": msg_time_berlin,
            "sender": sender_name.strip(),
            "reply_to": message.reply_to.reply_to_msg_id if message.reply_to else None,
        })
    
    messages.sort(key=lambda m: m["time"])
    print(f"Fetched {len(messages)} messages")
    
    await client.disconnect()
    
    # Analyze individual messages
    print("\n" + "=" * 60)
    print("Parsing Individual Messages with AI")
    print("=" * 60 + "\n")
    
    relevant_count = 0
    for msg in messages[:20]:  # Parse first 20 for demo
        result = parse_with_ai(msg["text"], timestamp=msg["time"])
        
        if result.is_relevant and not result.is_question:
            relevant_count += 1
            print(f"[{msg['time'].strftime('%a %H:%M')}] {msg['sender']}: {msg['text'][:50]}...")
            print(f"  → Queue: {result.queue_length or 'N/A'}, Wait: {result.wait_minutes or 'N/A'} min, "
                  f"Marker: {result.spatial_marker or 'N/A'}, Rejection: {result.rejection_rate or 'N/A'}")
            print(f"  → Confidence: {result.confidence:.0%}")
            print()
    
    print(f"Found {relevant_count} relevant queue reports in first 20 messages\n")
    
    # Full Klubnacht analysis
    print("=" * 60)
    print("Full Klubnacht Summary Analysis")
    print("=" * 60 + "\n")
    
    print("Analyzing all messages with AI... (this may take a moment)")
    summary = analyze_klubnacht_messages(messages)
    
    if "error" in summary:
        print(f"Error: {summary['error']}")
        return
    
    # Pretty print the summary
    print("\n📊 KLUBNACHT SUMMARY")
    print("-" * 40)
    
    if "overall_vibe" in summary:
        print(f"\n🎭 Overall Vibe: {summary['overall_vibe']}")
    
    if "average_rejection_rate" in summary:
        print(f"🚫 Average Rejection Rate: {summary['average_rejection_rate']}")
    
    if "peak_queue" in summary:
        peak = summary["peak_queue"]
        print(f"\n📈 Peak Queue: {peak.get('time', 'N/A')} - {peak.get('length', 'N/A')} ({peak.get('wait_minutes', '?')} min)")
    
    if "shortest_queue" in summary:
        short = summary["shortest_queue"]
        print(f"📉 Shortest Queue: {short.get('time', 'N/A')} - {short.get('length', 'N/A')} ({short.get('wait_minutes', '?')} min)")
    
    if "bouncers" in summary:
        print(f"\n👤 Bouncers mentioned:")
        for b in summary["bouncers"]:
            print(f"   - {b.get('name', 'Unknown')}: {b.get('strictness', 'N/A')} strictness")
    
    if "key_insights" in summary:
        print(f"\n💡 Key Insights:")
        for insight in summary["key_insights"]:
            print(f"   • {insight}")
    
    if "timeline" in summary:
        print(f"\n⏱️  Queue Timeline:")
        for entry in summary["timeline"][:10]:  # Show first 10
            print(f"   {entry.get('time', 'N/A')}: {entry.get('queue', 'N/A')} "
                  f"({entry.get('wait_minutes', '?')} min) - {entry.get('notes', '')}")
    
    # Save full summary to file
    output_file = "klubnacht_analysis_2026-02-07.json"
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n\n✅ Full analysis saved to {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
