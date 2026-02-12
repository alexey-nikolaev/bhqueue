"""
AI-powered Queue Parser using Claude.

Provides intelligent parsing of Telegram/Reddit messages about Berghain queue status.
Uses Claude to understand natural language, context, and nuance that regex cannot capture.

Falls back to regex-based parsing if AI is unavailable or disabled.
"""

import json
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from app.config import get_settings

# System prompt that gives Claude all the context it needs
SYSTEM_PROMPT = """You are an AI assistant specialized in parsing messages from the Berghain Berlin Telegram group to extract queue status information.

## About Berghain
Berghain is a legendary techno nightclub in Berlin, Germany. It operates from Saturday night (~23:00-midnight) through Monday morning (~6:00-12:00). The club is famous for its strict door policy - many people get rejected ("Nein") by the bouncers (Türsteher).

## Queue Geography
People queue along Am Wriezener Bahnhof street. From closest to furthest from the door:

**Main Queue Landmarks (in order from door):**
1. **Snake/Schlange** - The roped zigzag area right at the entrance (~15 min wait)
2. **Concrete blocks/Betonblöcke** - Past the snake (~30 min)
3. **Magic Cube** - A cubic structure (~45 min)
4. **Kiosk** - A small shop, common reference point (~60 min)
5. **Past Kiosk/Behind Kiosk** - Beyond the kiosk (~75 min)
6. **Späti** - A late-night convenience store (~90 min)
7. **Bridge/Brücke** - Railway bridge (~105 min)
8. **Around the block** - Queue wraps around (~120 min)
9. **Wriezener Straße** - Side street (~150 min)
10. **Metro sign/U-Bahn Schild** - Very long queue (~180+ min)

**Guestlist/GL Queue** (separate, shorter queue):
- Barriers, Love sculpture, Garten door, ATM, Park

## Bouncer Shifts
- Door staff typically changes around 08:00 and 18:00
- Famous bouncers: Sven Marquardt (distinctive face tattoos), Lars, Matrix, Mischa, Septum, NN

## Common Slang & Abbreviations
- "Q" or "q" = Queue
- "GL" = Guestlist
- "RSO" = Re-entry (Rauchen/Smoking Outside)
- "No q" / "0" = No queue
- "Nein" = Rejected
- "Schlange" = Queue (German)
- "Türsteher" = Bouncer (German)
- "50/50" = 50% rejection rate
- "friendly vibe" = Bouncers are accepting more people
- "strict" = High rejection rate

## Your Task
For each message, extract:

1. **queue_length**: One of: "none", "short", "medium", "long", "very_long", or null
   - "none"/"0"/empty: no queue, walk straight in
   - "short": snake area only, <30 min
   - "medium": to kiosk area, 30-60 min
   - "long": past kiosk, 60-120 min
   - "very_long": to metro sign or beyond, >120 min

2. **wait_minutes**: Estimated wait time in minutes (integer or null)

3. **spatial_marker**: The landmark mentioned (use canonical names from list above, or null)

4. **rejection_rate**: One of: "low", "medium", "high", "very_high", or null
   - "low": <20% rejection, friendly vibes
   - "medium": 20-50% rejection, normal
   - "high": 50-80% rejection
   - "very_high": >80% rejection, very strict

5. **bouncer**: Name of bouncer if mentioned (string or null)

6. **is_question**: true if the message is asking about queue, not reporting

7. **is_relevant**: true if message contains queue/door information, false for off-topic

8. **confidence**: 0.0 to 1.0, how confident you are in the extraction

## Response Format
Respond with a JSON object only, no other text:
```json
{
  "queue_length": "short" | "medium" | "long" | "very_long" | "none" | null,
  "wait_minutes": 45 | null,
  "spatial_marker": "Kiosk" | null,
  "rejection_rate": "low" | "medium" | "high" | "very_high" | null,
  "bouncer": "Sven" | null,
  "is_question": false,
  "is_relevant": true,
  "confidence": 0.85
}
```

## Important Notes
- Messages are often very short: "0", "Kios", "no q", "Q?"
- Context from replied-to messages helps interpretation
- German and English are both common
- Be conservative with confidence - only high confidence for clear, explicit reports
- "Q?" or "Queue?" alone is a question (is_question: true), not a report
- Off-topic messages (lost items, music discussion, etc.) should have is_relevant: false
"""


@dataclass
class AIParseResult:
    """Result from AI parsing."""
    queue_length: Optional[str] = None
    wait_minutes: Optional[int] = None
    spatial_marker: Optional[str] = None
    rejection_rate: Optional[str] = None
    bouncer: Optional[str] = None
    is_question: bool = False
    is_relevant: bool = True
    confidence: float = 0.5
    used_ai: bool = True
    error: Optional[str] = None


def parse_with_ai(
    message: str,
    parent_message: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> AIParseResult:
    """
    Parse a single message using Claude AI.
    
    Args:
        message: The message text to parse
        parent_message: Optional replied-to message for context
        timestamp: Optional timestamp for time-based context
        
    Returns:
        AIParseResult with extracted information
    """
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        return AIParseResult(
            used_ai=False,
            error="ANTHROPIC_API_KEY not configured",
            confidence=0.0,
        )
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        
        # Build the user message with context
        user_content = f"Message: {message}"
        if parent_message:
            user_content = f"Reply to: {parent_message}\n\n{user_content}"
        if timestamp:
            user_content = f"Time: {timestamp.strftime('%A %H:%M')}\n\n{user_content}"
        
        response = client.messages.create(
            model="claude-3-5-haiku-latest",  # Fast and cost-effective
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        
        # Parse the JSON response
        response_text = response.content[0].text.strip()
        
        # Handle potential markdown code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        data = json.loads(response_text)
        
        return AIParseResult(
            queue_length=data.get("queue_length"),
            wait_minutes=data.get("wait_minutes"),
            spatial_marker=data.get("spatial_marker"),
            rejection_rate=data.get("rejection_rate"),
            bouncer=data.get("bouncer"),
            is_question=data.get("is_question", False),
            is_relevant=data.get("is_relevant", True),
            confidence=data.get("confidence", 0.5),
            used_ai=True,
        )
        
    except json.JSONDecodeError as e:
        return AIParseResult(
            used_ai=True,
            error=f"Failed to parse AI response: {e}",
            confidence=0.0,
        )
    except Exception as e:
        return AIParseResult(
            used_ai=True,
            error=f"AI parsing error: {e}",
            confidence=0.0,
        )


def parse_batch_with_ai(
    messages: List[dict],
    max_batch_size: int = 10,
) -> List[AIParseResult]:
    """
    Parse multiple messages efficiently using Claude AI.
    
    Messages should be dicts with keys:
    - text: The message text
    - parent_text: Optional replied-to message
    - timestamp: Optional datetime
    
    Args:
        messages: List of message dicts to parse
        max_batch_size: Maximum messages per API call
        
    Returns:
        List of AIParseResult for each message
    """
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        return [
            AIParseResult(used_ai=False, error="ANTHROPIC_API_KEY not configured", confidence=0.0)
            for _ in messages
        ]
    
    if not messages:
        return []
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        
        results = []
        
        # Process in batches
        for i in range(0, len(messages), max_batch_size):
            batch = messages[i:i + max_batch_size]
            
            # Build batch request
            batch_content = "Parse each message and return a JSON array with one object per message:\n\n"
            for idx, msg in enumerate(batch):
                batch_content += f"### Message {idx + 1}\n"
                if msg.get("timestamp"):
                    batch_content += f"Time: {msg['timestamp'].strftime('%A %H:%M')}\n"
                if msg.get("parent_text"):
                    batch_content += f"Reply to: {msg['parent_text']}\n"
                batch_content += f"Text: {msg['text']}\n\n"
            
            batch_content += f"\nRespond with a JSON array of {len(batch)} objects, one for each message in order."
            
            response = client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=200 * len(batch),
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": batch_content}],
            )
            
            response_text = response.content[0].text.strip()
            
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            batch_data = json.loads(response_text)
            
            if not isinstance(batch_data, list):
                batch_data = [batch_data]
            
            for data in batch_data:
                results.append(AIParseResult(
                    queue_length=data.get("queue_length"),
                    wait_minutes=data.get("wait_minutes"),
                    spatial_marker=data.get("spatial_marker"),
                    rejection_rate=data.get("rejection_rate"),
                    bouncer=data.get("bouncer"),
                    is_question=data.get("is_question", False),
                    is_relevant=data.get("is_relevant", True),
                    confidence=data.get("confidence", 0.5),
                    used_ai=True,
                ))
        
        return results
        
    except Exception as e:
        # Return error results for all messages
        return [
            AIParseResult(used_ai=True, error=f"Batch parsing error: {e}", confidence=0.0)
            for _ in messages
        ]


def analyze_klubnacht_messages(
    messages: List[dict],
) -> dict:
    """
    Analyze a batch of Klubnacht messages and produce a summary.
    
    Args:
        messages: List of message dicts with text, timestamp, sender, etc.
        
    Returns:
        Summary dict with timeline, statistics, and insights
    """
    settings = get_settings()
    
    if not settings.anthropic_api_key:
        return {"error": "ANTHROPIC_API_KEY not configured"}
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        
        # Format messages for analysis
        messages_text = ""
        for msg in messages:
            time_str = msg.get("timestamp", msg.get("time", "")).strftime("%a %H:%M") if hasattr(msg.get("timestamp", msg.get("time", "")), "strftime") else str(msg.get("time", ""))
            sender = msg.get("sender", "Unknown")
            text = msg.get("text", msg.get("content", ""))
            reply = f" [reply]" if msg.get("reply_to") else ""
            messages_text += f"[{time_str}] {sender}{reply}: {text}\n"
        
        analysis_prompt = f"""Analyze these Berghain Telegram group messages from a Klubnacht weekend and provide:

1. **Queue Timeline**: Key queue length changes throughout the event
2. **Peak Times**: When was the queue longest/shortest
3. **Door Staff**: Which bouncers were mentioned and when
4. **Rejection Rate**: How strict was the door throughout the night
5. **Overall Vibe**: General atmosphere based on messages

Messages:
{messages_text}

Respond with a JSON object:
```json
{{
  "timeline": [
    {{"time": "Sat 23:00", "queue": "short", "wait_minutes": 20, "notes": "Opening, building up"}},
    ...
  ],
  "peak_queue": {{"time": "Sun 03:00", "length": "medium", "wait_minutes": 60}},
  "shortest_queue": {{"time": "Sun 09:00", "length": "none", "wait_minutes": 0}},
  "bouncers": [{{"name": "Sven", "times": ["Sun 21:00-?"], "strictness": "medium"}}],
  "average_rejection_rate": "medium",
  "overall_vibe": "Relatively calm night with consistent medium rejection rate",
  "key_insights": ["Queue was mostly short to none", "High rejection despite short queue"]
}}
```"""
        
        response = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=1500,
            system="You analyze Berghain queue data from Telegram messages. Be concise and data-focused.",
            messages=[{"role": "user", "content": analysis_prompt}],
        )
        
        response_text = response.content[0].text.strip()
        
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()
        
        return json.loads(response_text)
        
    except Exception as e:
        return {"error": str(e)}
