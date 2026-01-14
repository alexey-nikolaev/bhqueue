"""
Telegram monitor service for reading queue updates from Berghain Berlin group.

Uses Telethon to connect to Telegram and read messages from the public group.
Parses messages to extract queue time estimates and spatial markers.
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

from telethon import TelegramClient
from telethon.tl.types import Message

from app.config import get_settings
from app.utils.timezone import to_utc

settings = get_settings()

# Telegram group to monitor
BERGHAIN_GROUP = "berghainberlin"

# Patterns for extracting queue information
TIME_PATTERNS = [
    # "1:30h" or "1.30h" or "1:30 hours" (hours:minutes format) - check first!
    (r'\b(\d+)[:\.](\d{2})\s*(?:h|hours?|hrs?)\b', 'hm'),
    # "2 hours", "2h", "2 hr", "2hrs" (but not "1:30h" which is caught above)
    (r'(?<![:\d])(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b', 60),
    # "30 minutes", "30 min", "30m", "30 mins"  
    (r'(\d+)\s*(?:minutes?|mins?|m)\b', 1),
    # "no queue", "keine schlange", "empty", "no Q"
    (r'\b(?:no queue|keine schlange|no line|empty|leer|niemand|no q|0 q)\b', 0),
]

# Spatial markers - common landmarks mentioned in queue descriptions
# Based on real messages from the Telegram group
SPATIAL_MARKERS = [
    # Actual queue location markers
    "wriezener", "wriezener strasse", "wriezener str",
    "späti", "spati", "spätkauf",
    "kiosk",
    "snake",  # The snake/winding part of the queue
    "parkplatz", "parking",
    "zaun", "fence",
    # Note: "door", "entrance", "gate" are NOT spatial markers
    # - they're usually about door policy, not queue position
]

# Keywords that indicate queue-related messages
QUEUE_KEYWORDS = [
    "queue", "schlange", "line", "waiting", "warten",
    "wait", "wartezeit", "hour", "stunde", "minute",
    "rein", "rejected", "abgelehnt", "inside", "drin",
]


def extract_wait_time(text: str) -> Optional[int]:
    """
    Extract estimated wait time in minutes from message text.
    
    Returns:
        Estimated wait time in minutes, or None if not found
    """
    text_lower = text.lower()
    
    for pattern, multiplier in TIME_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            if multiplier == 0:
                # "no queue" pattern
                return 0
            elif multiplier == 'hm':
                # hours:minutes format
                hours = int(match.group(1))
                minutes = int(match.group(2))
                return hours * 60 + minutes
            else:
                value = float(match.group(1))
                return int(value * multiplier)
    
    return None


def extract_spatial_marker(text: str) -> Optional[str]:
    """
    Extract spatial marker (landmark) from message text.
    
    Returns:
        Spatial marker name, or None if not found
    """
    text_lower = text.lower()
    
    # Check for markers in order of specificity (longer matches first)
    if "wriezener str" in text_lower or "wriezener strasse" in text_lower:
        return "wriezener"
    if "wriezener" in text_lower:
        return "wriezener"
    if any(m in text_lower for m in ["späti", "spati", "spätkauf"]):
        return "späti"
    if "kiosk" in text_lower:
        return "kiosk"
    if "snake" in text_lower:
        return "snake"
    if any(m in text_lower for m in ["parkplatz", "parking"]):
        return "parking"
    if any(m in text_lower for m in ["zaun", "fence"]):
        return "fence"
    
    return None


def is_queue_related(text: str) -> bool:
    """Check if a message is likely about queue status."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in QUEUE_KEYWORDS)


def calculate_confidence(text: str, wait_time: Optional[int]) -> float:
    """
    Calculate confidence score for a parsed message.
    
    Higher confidence for:
    - Explicit time mentions
    - Multiple queue keywords
    - Recent timestamps
    """
    confidence = 0.5  # Base confidence
    
    text_lower = text.lower()
    
    # Boost for explicit time
    if wait_time is not None:
        confidence += 0.2
    
    # Boost for multiple queue keywords
    keyword_count = sum(1 for kw in QUEUE_KEYWORDS if kw in text_lower)
    confidence += min(keyword_count * 0.05, 0.2)
    
    # Boost for spatial markers
    if extract_spatial_marker(text):
        confidence += 0.1
    
    return min(confidence, 1.0)


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
            
            # Skip non-queue messages
            if not is_queue_related(message.text):
                continue
            
            # Parse the message
            wait_time = extract_wait_time(message.text)
            spatial_marker = extract_spatial_marker(message.text)
            confidence = calculate_confidence(message.text, wait_time)
            
            parsed_messages.append({
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "estimated_wait_minutes": wait_time,
                "spatial_marker": spatial_marker,
                "confidence": confidence,
                "posted_at": to_utc(message.date),
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
            
            wait_time = extract_wait_time(message.text)
            spatial_marker = extract_spatial_marker(message.text)
            confidence = calculate_confidence(message.text, wait_time)
            
            parsed = {
                "source": "telegram",
                "source_id": str(message.id),
                "raw_text": message.text,
                "estimated_wait_minutes": wait_time,
                "spatial_marker": spatial_marker,
                "confidence": confidence,
                "posted_at": to_utc(message.date),
            }
            
            await callback(parsed)
        
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
