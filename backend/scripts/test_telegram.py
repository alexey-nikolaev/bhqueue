"""
Test script for Telegram monitor.

Run with: python -m scripts.test_telegram
"""

import asyncio
from datetime import datetime, timedelta

from app.services.telegram_monitor import (
    TelegramMonitor,
    extract_wait_time,
    extract_spatial_marker,
    is_queue_related,
)
from app.utils.timezone import BERLIN_TZ


def test_parsing():
    """Test message parsing functions."""
    print("Testing message parsing...\n")
    
    test_messages = [
        "Queue is about 2 hours right now",
        "No queue at the moment!",
        "Waiting for 30 minutes so far",
        "Schlange bis zum Späti",
        "1:30h wait time",  # Should be 90 minutes
        "Got in after 45 min",
        "Queue to the corner, maybe 1h",
        "Beautiful weather today",  # Not queue related
        "keine schlange, direkt rein",
        "Queue Wriezener strasse",  # Real message from last Klubnacht
        "Queue bit more than kiosk",  # Real message
        "no Q",  # Short form
        "can they turn me away at the door?",  # Should NOT match spatial marker
        "line cutter at snake",  # Snake is a spatial marker
    ]
    
    for msg in test_messages:
        is_related = is_queue_related(msg)
        wait_time = extract_wait_time(msg)
        marker = extract_spatial_marker(msg)
        
        print(f"Message: \"{msg}\"")
        print(f"  Queue related: {is_related}")
        print(f"  Wait time: {wait_time} minutes")
        print(f"  Spatial marker: {marker}")
        print()


async def test_last_klubnacht():
    """Fetch messages from the last Klubnacht (last weekend)."""
    print("\n" + "="*60)
    print("Fetching messages from LAST KLUBNACHT...")
    print("="*60 + "\n")
    
    monitor = TelegramMonitor()
    
    try:
        connected = await monitor.connect()
        if not connected:
            print("Failed to connect.")
            return
        
        from telethon.tl.types import Message
        
        # Calculate last Klubnacht times (last Saturday 21:00 to Monday 08:00 Berlin time)
        now_berlin = datetime.now(BERLIN_TZ)
        today = now_berlin.date()
        weekday = today.weekday()
        
        # Find the most recent Saturday
        days_since_saturday = (weekday - 5) % 7
        if days_since_saturday == 0 and now_berlin.hour < 8:
            # It's Saturday before 8am, use last week's Saturday
            days_since_saturday = 7
        
        last_saturday = today - timedelta(days=days_since_saturday)
        
        # Klubnacht window: Saturday 21:00 to Monday 08:00 Berlin time
        klubnacht_start = BERLIN_TZ.localize(
            datetime.combine(last_saturday, datetime.min.time().replace(hour=21, minute=0))
        )
        klubnacht_end = BERLIN_TZ.localize(
            datetime.combine(last_saturday + timedelta(days=2), datetime.min.time().replace(hour=8, minute=0))
        )
        
        print(f"Last Klubnacht window (Berlin time):")
        print(f"  Start: {klubnacht_start}")
        print(f"  End:   {klubnacht_end}")
        print()
        
        # Fetch messages
        all_messages = []
        queue_messages = []
        
        async for message in monitor.client.iter_messages(
            "berghainberlin",
            limit=500,  # Fetch more to cover the weekend
            offset_date=klubnacht_end,
        ):
            if not isinstance(message, Message) or not message.text:
                continue
            
            msg_time = message.date
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=BERLIN_TZ)
            
            # Only messages within Klubnacht window
            if msg_time < klubnacht_start:
                break
            if msg_time > klubnacht_end:
                continue
            
            all_messages.append(message)
            
            if is_queue_related(message.text):
                wait_time = extract_wait_time(message.text)
                marker = extract_spatial_marker(message.text)
                queue_messages.append({
                    "time": msg_time,
                    "text": message.text,
                    "wait_time": wait_time,
                    "marker": marker,
                })
        
        print(f"Total messages during Klubnacht: {len(all_messages)}")
        print(f"Queue-related messages: {len(queue_messages)}")
        print()
        
        if queue_messages:
            print("="*60)
            print("QUEUE-RELATED MESSAGES:")
            print("="*60)
            
            for msg in queue_messages:
                print(f"\n[{msg['time'].strftime('%a %H:%M')}]")
                print(f"  {msg['text'][:200]}")
                if msg['wait_time'] is not None:
                    print(f"  → Parsed wait time: {msg['wait_time']} minutes")
                if msg['marker']:
                    print(f"  → Spatial marker: {msg['marker']}")
            
            # Summary statistics
            wait_times = [m['wait_time'] for m in queue_messages if m['wait_time'] is not None]
            markers = [m['marker'] for m in queue_messages if m['marker']]
            
            print("\n" + "="*60)
            print("SUMMARY:")
            print("="*60)
            print(f"Messages with parsed wait times: {len(wait_times)}")
            if wait_times:
                print(f"  Min: {min(wait_times)} min")
                print(f"  Max: {max(wait_times)} min")
                print(f"  Avg: {sum(wait_times)/len(wait_times):.0f} min")
            
            print(f"\nSpatial markers found: {len(markers)}")
            if markers:
                from collections import Counter
                marker_counts = Counter(markers)
                for marker, count in marker_counts.most_common():
                    print(f"  {marker}: {count}")
        else:
            print("No queue-related messages found during last Klubnacht.")
            print("\nShowing some sample messages from that time:")
            for msg in all_messages[:10]:
                print(f"\n[{msg.date.strftime('%a %H:%M')}] {msg.text[:150]}")
    
    finally:
        await monitor.disconnect()


async def main():
    # Test parsing first (no connection needed)
    test_parsing()
    
    # Test fetching from last Klubnacht
    await test_last_klubnacht()


if __name__ == "__main__":
    asyncio.run(main())
