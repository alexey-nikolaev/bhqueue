"""
Queue Parser Service

Unified parsing logic for queue updates from all sources (Reddit, Telegram).
All parsing happens here so we have consistent logic and easy maintenance.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class ParsedQueueData:
    """Structured queue information extracted from text."""
    wait_minutes: Optional[int] = None
    queue_length: Optional[str] = None  # 'none', 'short', 'medium', 'long', 'very_long'
    spatial_marker: Optional[str] = None
    rejection_mentioned: bool = False
    entry_mentioned: bool = False
    confidence: float = 0.5


# Known spatial markers around Berghain
SPATIAL_MARKERS = [
    ('wriezener', 'Wriezener Straße'),
    ('kiosk', 'Kiosk'),
    ('snack', 'Snack shop'),
    ('späti', 'Späti'),
    ('corner', 'Corner'),
    ('around the block', 'Around the block'),
    ('bridge', 'Bridge'),
    ('entrance', 'Entrance'),
    ('door', 'Door'),
    ('halfway', 'Halfway'),
]

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


def parse_queue_message(text: str) -> ParsedQueueData:
    """
    Parse a message (from Reddit or Telegram) for queue information.
    
    Args:
        text: The raw message text to parse
        
    Returns:
        ParsedQueueData with extracted information
    """
    if not text:
        return ParsedQueueData()
    
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
    
    # Parse spatial markers
    for marker_key, marker_name in SPATIAL_MARKERS:
        if marker_key in lower_text:
            result.spatial_marker = marker_name
            confidence_factors.append(0.6)
            break
    
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


def estimate_wait_from_spatial_marker(marker: str) -> Optional[int]:
    """
    Estimate wait time based on spatial marker.
    
    This uses historical averages and will be refined over time
    as we collect more data.
    
    Args:
        marker: The spatial marker name
        
    Returns:
        Estimated wait time in minutes, or None if unknown
    """
    # These are rough estimates based on typical queue movement
    # ~50-100 people per hour, ~2m per person spacing
    estimates = {
        'Entrance': 5,
        'Door': 10,
        'Kiosk': 30,
        'Späti': 45,
        'Snack shop': 45,
        'Corner': 60,
        'Halfway': 75,
        'Wriezener Straße': 90,
        'Around the block': 120,
        'Bridge': 150,
    }
    return estimates.get(marker)


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
