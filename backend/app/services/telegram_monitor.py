"""
Telegram monitor service for reading queue updates from Berghain Berlin group.

Uses Telethon to connect to Telegram and read messages from the public group.
Sends raw messages to the unified parser for processing.
Supports context-aware parsing by including replied-to messages.
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
    "wriezener", "kiosk", "späti", "how", "wie",
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
        self._message_cache: dict[int, str] = {}  # Cache for replied-to messages
    
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
    
    async def _get_replied_message_text(self, message: Message) -> Optional[str]:
        """
        Get the text of the message this one is replying to.
        
        Args:
            message: The message that might be a reply
            
        Returns:
            Text of the replied-to message, or None
        """
        if not message.reply_to:
            return None
        
        reply_to_id = message.reply_to.reply_to_msg_id
        if not reply_to_id:
            return None
        
        # Check cache first
        if reply_to_id in self._message_cache:
            return self._message_cache[reply_to_id]
        
        try:
            # Fetch the replied-to message
            replied_msg = await self.client.get_messages(
                BERGHAIN_GROUP,
                ids=reply_to_id
            )
            if replied_msg and replied_msg.text:
                # Cache it
                self._message_cache[reply_to_id] = replied_msg.text
                # Keep cache size manageable
                if len(self._message_cache) > 1000:
                    # Remove oldest entries
                    oldest_keys = list(self._message_cache.keys())[:500]
                    for key in oldest_keys:
                        del self._message_cache[key]
                return replied_msg.text
        except Exception as e:
            print(f"Error fetching replied message: {e}")
        
        return None
    
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
        
        # First pass: cache all messages for reply lookups
        messages_list = []
        async for message in self.client.iter_messages(
            BERGHAIN_GROUP,
            limit=limit,
        ):
            if isinstance(message, Message) and message.text:
                self._message_cache[message.id] = message.text
                messages_list.append(message)
        
        # Second pass: process messages with context
        for message in messages_list:
            # Skip old messages
            if message.date.replace(tzinfo=None) < since_time:
                continue
            
            # Pre-filter: skip messages that don't look queue-related
            if not is_queue_related(message.text):
                continue
            
            # Get replied-to message for context
            parent_text = await self._get_replied_message_text(message)
            
            # Use the unified parser with context
            parsed = parse_queue_message(message.text, parent_text=parent_text)
            
            # Skip low-confidence parses
            if parsed.confidence < 0.2:
                continue
            
            parsed_messages.append({
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "parent_text": parent_text,
                "parsed_wait_minutes": parsed.wait_minutes,
                "parsed_queue_length": parsed.queue_length,
                "parsed_spatial_marker": parsed.spatial_marker,
                "confidence": parsed.confidence,
                "used_context": parsed.used_context,
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
            if not message.text:
                return
            
            # Cache this message for future reply lookups
            self._message_cache[message.id] = message.text
            
            # Pre-filter
            if not is_queue_related(message.text):
                return
            
            # Get replied-to message for context
            parent_text = await self._get_replied_message_text(message)
            
            # Use the unified parser with context
            parsed = parse_queue_message(message.text, parent_text=parent_text)
            
            # Skip low-confidence parses
            if parsed.confidence < 0.2:
                return
            
            data = {
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "parent_text": parent_text,
                "parsed_wait_minutes": parsed.wait_minutes,
                "parsed_queue_length": parsed.queue_length,
                "parsed_spatial_marker": parsed.spatial_marker,
                "confidence": parsed.confidence,
                "used_context": parsed.used_context,
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
