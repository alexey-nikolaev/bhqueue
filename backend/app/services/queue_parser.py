"""
Queue Parser Service

Unified parsing logic for queue updates from all sources (Reddit, Telegram).
All parsing happens here so we have consistent logic and easy maintenance.

Supports context-aware parsing: combines parent message + reply for better accuracy.
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ParsedQueueData:
    """Structured queue information extracted from text."""
    wait_minutes: Optional[int] = None
    queue_length: Optional[str] = None  # 'none', 'short', 'medium', 'long', 'very_long'
    spatial_marker: Optional[str] = None
    marker_modifier: Optional[int] = None  # meters past (+) or before (-) marker
    rejection_mentioned: bool = False
    entry_mentioned: bool = False
    confidence: float = 0.5
    used_context: bool = False  # True if parent context helped parsing


# Known spatial markers around Berghain (ordered by distance from entrance)
# Format: (keyword, display_name, base_distance_meters)
SPATIAL_MARKERS = [
    ('wriezener', 'Wriezener Straße', 400),
    ('around the block', 'Around the block', 350),
    ('bridge', 'Bridge', 300),
    ('halfway', 'Halfway', 200),
    ('corner', 'Corner', 150),
    ('späti', 'Späti', 120),
    ('spati', 'Späti', 120),  # Without umlaut
    ('snack', 'Snack shop', 100),
    ('kiosk', 'Kiosk', 80),
    ('entrance', 'Entrance', 10),
    ('door', 'Door', 5),
]

# Build lookup dict for marker distances
MARKER_DISTANCES = {name: dist for _, name, dist in SPATIAL_MARKERS}

# Queue length patterns
QUEUE_LENGTH_PATTERNS = [
    (r'\b(no\s*queue|empty|walk[\s-]*in|straight\s*in)\b', 'none'),
    (r'\b(short|small|quick|fast|minimal)\b', 'short'),
    (r'\b(medium|moderate|normal|average|decent)\b', 'medium'),
    (r'\b(long|big|large|substantial)\b', 'long'),
    (r'\b(huge|massive|insane|crazy|enormous|never\s*seen|longest)\b', 'very_long'),
]

# Wait time patterns
WAIT_TIME_PATTERNS = [
    # "2h wait", "2 hours", "2h queue"
    (r'(\d+(?:\.\d+)?)\s*h(?:ours?)?\s*(?:wait|queue|line)?', 'hours'),
    # "90 min wait", "90 minutes"
    (r'(\d+)\s*min(?:utes?)?\s*(?:wait|queue|line)?', 'minutes'),
    # "wait: 2h", "wait time: 90min"
    (r'wait(?:ing)?(?:\s*time)?:?\s*(\d+(?:\.\d+)?)\s*h', 'hours'),
    (r'wait(?:ing)?(?:\s*time)?:?\s*(\d+)\s*min', 'minutes'),
    # "waited 2 hours", "been waiting 90 min"
    (r'wait(?:ed|ing)\s+(?:for\s+)?(\d+(?:\.\d+)?)\s*h', 'hours'),
    (r'wait(?:ed|ing)\s+(?:for\s+)?(\d+)\s*min', 'minutes'),
    # "~2h", "approx 90min"
    (r'[~≈]?\s*(\d+(?:\.\d+)?)\s*h(?:ours?)?(?:\s*wait)?', 'hours'),
    (r'[~≈]?\s*(\d+)\s*min(?:utes?)?(?:\s*wait)?', 'minutes'),
]

# Patterns that indicate a question about the queue (used for context detection)
QUEUE_QUESTION_PATTERNS = [
    r'\b(how\s*(is|long|big)|what\'?s|status|update)\b.*(queue|line|q|schlange|wait)',
    r'\b(queue|line|q|schlange|wait).*(how|what|\?)',
    r'\bhow\s*is\s*(it|the|berghain)\b',
    r'\bany\s*(update|news|info)\b',
    r'\bcurrent\s*(status|situation|wait)\b',
]


def is_queue_question(text: str) -> bool:
    """Check if text is asking about queue status."""
    lower_text = text.lower()
    for pattern in QUEUE_QUESTION_PATTERNS:
        if re.search(pattern, lower_text, re.IGNORECASE):
            return True
    return '?' in text and any(w in lower_text for w in ['queue', 'line', 'wait', 'q', 'schlange', 'how', 'long'])


def _parse_spatial_marker_with_modifier(text: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse spatial marker with optional distance modifier.
    
    Handles patterns like:
    - "Kiosk +10m" (10 meters past kiosk)
    - "past kiosk" (slightly past)
    - "before kiosk" (slightly before)
    - "almost at kiosk" (slightly before)
    
    Returns:
        Tuple of (marker_name, modifier_meters)
        modifier is positive for "past", negative for "before"
    """
    lower_text = text.lower()
    
    for marker_key, marker_name, _ in SPATIAL_MARKERS:
        if marker_key not in lower_text:
            continue
        
        # Found marker, now look for modifiers
        modifier = None
        
        # Pattern: "marker +10m" or "marker +10 m" or "marker + 10m"
        plus_pattern = rf'{marker_key}\s*\+\s*(\d+)\s*m\b'
        match = re.search(plus_pattern, lower_text)
        if match:
            modifier = int(match.group(1))
            return marker_name, modifier
        
        # Pattern: "marker -10m" (unlikely but handle it)
        minus_pattern = rf'{marker_key}\s*-\s*(\d+)\s*m\b'
        match = re.search(minus_pattern, lower_text)
        if match:
            modifier = -int(match.group(1))
            return marker_name, modifier
        
        # Pattern: "past marker", "beyond marker", "after marker"
        past_patterns = [
            rf'(past|beyond|after)\s+(?:the\s+)?{marker_key}',
            rf'{marker_key}\s+(?:and\s+)?(past|beyond|further)',
        ]
        for pattern in past_patterns:
            if re.search(pattern, lower_text):
                modifier = 20  # Assume ~20m past
                return marker_name, modifier
        
        # Pattern: "before marker", "almost at marker", "approaching marker"
        before_patterns = [
            rf'(before|almost\s+at|approaching|nearly\s+at)\s+(?:the\s+)?{marker_key}',
            rf'(almost|nearly|just\s+before)\s+{marker_key}',
        ]
        for pattern in before_patterns:
            if re.search(pattern, lower_text):
                modifier = -15  # Assume ~15m before
                return marker_name, modifier
        
        # Pattern: "to marker" or "at marker" (no modifier)
        return marker_name, None
    
    return None, None


def parse_queue_message(text: str, parent_text: Optional[str] = None) -> ParsedQueueData:
    """
    Parse a message (from Reddit or Telegram) for queue information.
    
    Supports context-aware parsing: if the message itself yields low results
    but there's a parent message asking about the queue, we combine them.
    
    Args:
        text: The raw message text to parse
        parent_text: Optional parent/replied-to message for context
        
    Returns:
        ParsedQueueData with extracted information
    """
    if not text:
        return ParsedQueueData()
    
    # First, try parsing just the message itself
    result = _parse_text(text)
    
    # If we got good results, return them
    if result.confidence >= 0.5:
        return result
    
    # If we have parent context and it's a queue question, try combining
    if parent_text and is_queue_question(parent_text):
        # The reply is likely an answer to the queue question
        # Combine parent question + reply for context
        combined_text = f"{parent_text} {text}"
        combined_result = _parse_text(combined_text)
        
        # If combined parsing found more info, use it
        if combined_result.confidence > result.confidence:
            combined_result.used_context = True
            # Boost confidence since context helped
            combined_result.confidence = min(0.95, combined_result.confidence + 0.1)
            return combined_result
    
    # Even without question context, short replies to any message might be answers
    # e.g., "To the kiosk" as a standalone reply
    if parent_text and len(text.split()) <= 5:
        combined_text = f"{parent_text} Answer: {text}"
        combined_result = _parse_text(combined_text)
        
        if combined_result.confidence > result.confidence:
            combined_result.used_context = True
            return combined_result
    
    return result


def _parse_text(text: str) -> ParsedQueueData:
    """
    Internal function to parse text for queue information.
    
    Args:
        text: The text to parse
        
    Returns:
        ParsedQueueData with extracted information
    """
    lower_text = text.lower()
    result = ParsedQueueData()
    confidence_factors = []
    
    # Parse wait time
    for pattern, unit in WAIT_TIME_PATTERNS:
        match = re.search(pattern, lower_text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            if unit == 'hours':
                result.wait_minutes = round(value * 60)
            else:
                result.wait_minutes = round(value)
            confidence_factors.append(0.8)  # High confidence when we find explicit time
            break
    
    # Parse spatial markers with modifiers
    marker, modifier = _parse_spatial_marker_with_modifier(text)
    if marker:
        result.spatial_marker = marker
        result.marker_modifier = modifier
        confidence_factors.append(0.6)
        if modifier is not None:
            confidence_factors.append(0.2)  # Bonus for having modifier info
    
    # Parse queue length description
    for pattern, length in QUEUE_LENGTH_PATTERNS:
        if re.search(pattern, lower_text, re.IGNORECASE):
            result.queue_length = length
            confidence_factors.append(0.5)
            break
    
    # Check for rejection mentions
    rejection_patterns = [
        r'\b(rejected|rejection|turned\s*away|didn\'?t\s*get\s*in|refused)\b',
        r'\b(bouncer|türsteher)\s*(said\s*no|rejected)',
    ]
    for pattern in rejection_patterns:
        if re.search(pattern, lower_text, re.IGNORECASE):
            result.rejection_mentioned = True
            confidence_factors.append(0.4)
            break
    
    # Check for entry mentions
    entry_patterns = [
        r'\b(got\s*in|made\s*it|inside|entered|admitted)\b',
        r'\b(we\'?re\s*in|i\'?m\s*in|finally\s*in)\b',
        r'\byes\b.*\b(in|inside|made)\b',
        r'\b(yes|yeah|yep|ja)\b',  # Short affirmatives (useful with context)
    ]
    for pattern in entry_patterns:
        if re.search(pattern, lower_text, re.IGNORECASE):
            result.entry_mentioned = True
            confidence_factors.append(0.4)
            break
    
    # Calculate overall confidence
    if confidence_factors:
        result.confidence = min(0.95, sum(confidence_factors) / len(confidence_factors) + 0.1 * len(confidence_factors))
    else:
        result.confidence = 0.1  # Very low confidence if nothing was parsed
    
    return result


def estimate_wait_from_spatial_marker(marker: str, modifier_meters: Optional[int] = None) -> Optional[int]:
    """
    Estimate wait time based on spatial marker and optional distance modifier.
    
    Uses historical averages. Queue typically moves at ~50-100 people per hour,
    with ~2m spacing per person, so ~25-50m per hour = ~2 min per meter.
    
    Args:
        marker: The spatial marker name
        modifier_meters: Additional meters past (+) or before (-) the marker
        
    Returns:
        Estimated wait time in minutes, or None if unknown
    """
    base_distance = MARKER_DISTANCES.get(marker)
    if base_distance is None:
        return None
    
    # Apply modifier
    total_distance = base_distance
    if modifier_meters:
        total_distance += modifier_meters
    
    # Convert distance to time: ~2.5 min per 10 meters (based on typical queue movement)
    # This assumes ~4m/min queue movement = 240m/hour = ~80-120 people/hour
    wait_minutes = round(total_distance * 0.25)  # 0.25 min per meter = 15 min per 60m
    
    return max(0, wait_minutes)


def estimate_wait_from_queue_length(length: str) -> Optional[int]:
    """
    Estimate wait time based on queue length description.
    
    Args:
        length: Queue length category ('none', 'short', etc.)
        
    Returns:
        Estimated wait time in minutes
    """
    estimates = {
        'none': 0,
        'short': 15,
        'medium': 45,
        'long': 90,
        'very_long': 150,
    }
    return estimates.get(length)
