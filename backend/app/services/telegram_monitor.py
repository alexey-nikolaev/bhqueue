"""
Telegram monitor service for reading queue updates from Berghain Berlin group.

Uses Telethon to connect to Telegram and read messages from the public group.
Sends raw messages to the unified parser for processing.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Message

from app.config import get_settings
from app.utils.timezone import to_utc
from app.services.queue_parser import parse_queue_message

settings = get_settings()

# Telegram group to monitor
BERGHAIN_GROUP = "berghainberlin"

# Keywords that indicate queue-related messages (for pre-filtering)
QUEUE_KEYWORDS = [
    "queue", "schlange", "line", "waiting", "warten",
    "wait", "wartezeit", "hour", "stunde", "minute",
    "rein", "rejected", "abgelehnt", "inside", "drin",
    "wriezener", "kiosk", "späti",
]


def is_queue_related(text: str) -> bool:
    """Check if a message is likely about queue status."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in QUEUE_KEYWORDS)


class TelegramMonitor:
    """
    Monitors Telegram group for queue updates.
    """
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.session_name = "bhqueue_session"
    
    async def connect(self) -> bool:
        """
        Connect to Telegram.
        
        Returns True if connected successfully.
        """
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            print("Telegram credentials not configured")
            return False
        
        try:
            api_id = int(settings.telegram_api_id)
        except (ValueError, TypeError):
            print("Invalid TELEGRAM_API_ID")
            return False
        
        self.client = TelegramClient(
            self.session_name,
            api_id,
            settings.telegram_api_hash,
        )
        
        await self.client.start(phone=settings.telegram_phone)
        print("Connected to Telegram")
        return True
    
    async def disconnect(self):
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()
            print("Disconnected from Telegram")
    
    async def get_recent_messages(
        self,
        limit: int = 100,
        since_hours: int = 24,
    ) -> list[dict]:
        """
        Get recent queue-related messages from the Berghain group.
        
        Args:
            limit: Maximum number of messages to fetch
            since_hours: Only get messages from the last N hours
            
        Returns:
            List of parsed message data
        """
        if not self.client:
            raise RuntimeError("Not connected to Telegram")
        
        since_time = datetime.utcnow() - timedelta(hours=since_hours)
        parsed_messages = []
        
        async for message in self.client.iter_messages(
            BERGHAIN_GROUP,
            limit=limit,
        ):
            if not isinstance(message, Message) or not message.text:
                continue
            
            # Skip old messages
            if message.date.replace(tzinfo=None) < since_time:
                break
            
            # Pre-filter: skip messages that don't look queue-related
            if not is_queue_related(message.text):
                continue
            
            # Use the unified parser
            parsed = parse_queue_message(message.text)
            
            # Skip low-confidence parses
            if parsed.confidence < 0.2:
                continue
            
            parsed_messages.append({
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "parsed_wait_minutes": parsed.wait_minutes,
                "parsed_queue_length": parsed.queue_length,
                "parsed_spatial_marker": parsed.spatial_marker,
                "confidence": parsed.confidence,
                "source_timestamp": to_utc(message.date),
            })
        
        return parsed_messages
    
    async def listen_for_updates(self, callback):
        """
        Listen for new messages in real-time.
        
        Args:
            callback: Async function to call with each new queue-related message
        """
        if not self.client:
            raise RuntimeError("Not connected to Telegram")
        
        from telethon import events
        
        @self.client.on(events.NewMessage(chats=BERGHAIN_GROUP))
        async def handler(event):
            message = event.message
            if not message.text or not is_queue_related(message.text):
                return
            
            # Use the unified parser
            parsed = parse_queue_message(message.text)
            
            # Skip low-confidence parses
            if parsed.confidence < 0.2:
                return
            
            data = {
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "parsed_wait_minutes": parsed.wait_minutes,
                "parsed_queue_length": parsed.queue_length,
                "parsed_spatial_marker": parsed.spatial_marker,
                "confidence": parsed.confidence,
                "source_timestamp": to_utc(message.date),
            }
            
            await callback(data)
        
        print(f"Listening for messages in {BERGHAIN_GROUP}...")
        await self.client.run_until_disconnected()


# Singleton instance
_monitor: Optional[TelegramMonitor] = None


async def get_telegram_monitor() -> TelegramMonitor:
    """Get or create the Telegram monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = TelegramMonitor()
        await _monitor.connect()
    return _monitor
