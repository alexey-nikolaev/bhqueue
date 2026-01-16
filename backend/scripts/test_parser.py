#!/usr/bin/env python3
"""
Test script for the queue parser.

Usage:
    python scripts/test_parser.py "your message here"
    
Or run without arguments to test with example messages.
"""

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.queue_parser import parse_queue_message, estimate_wait_from_spatial_marker, estimate_wait_from_queue_length


def test_message(text: str, parent_text: str = None) -> None:
    """Parse a message and print the results."""
    print(f"\n{'='*60}")
    if parent_text:
        print(f"PARENT: {parent_text}")
        print(f"REPLY:  {text}")
    else:
        print(f"INPUT: {text}")
    print(f"{'='*60}")
    
    result = parse_queue_message(text, parent_text=parent_text)
    
    print(f"  Wait minutes:    {result.wait_minutes}")
    print(f"  Queue length:    {result.queue_length}")
    print(f"  Spatial marker:  {result.spatial_marker}")
    if result.marker_modifier:
        print(f"  Marker modifier: {'+' if result.marker_modifier > 0 else ''}{result.marker_modifier}m")
    print(f"  Rejection:       {result.rejection_mentioned}")
    print(f"  Entry:           {result.entry_mentioned}")
    print(f"  Confidence:      {result.confidence:.2f}")
    if result.used_context:
        print(f"  ✓ Context helped!")
    
    # Show estimated wait if we have spatial marker or queue length but no explicit time
    if not result.wait_minutes:
        if result.spatial_marker:
            est = estimate_wait_from_spatial_marker(result.spatial_marker, result.marker_modifier)
            if est:
                print(f"  (Estimated from marker: ~{est} min)")
        if result.queue_length:
            est = estimate_wait_from_queue_length(result.queue_length)
            if est is not None:
                print(f"  (Estimated from length: ~{est} min)")


def main():
    if len(sys.argv) > 1:
        # Check for --parent flag for context testing
        if "--parent" in sys.argv:
            parent_idx = sys.argv.index("--parent")
            parent = sys.argv[parent_idx + 1]
            # Everything before --parent is the reply
            reply = " ".join(sys.argv[1:parent_idx])
            test_message(reply, parent_text=parent)
        else:
            # Parse command line argument (no context)
            text = " ".join(sys.argv[1:])
            test_message(text)
    else:
        # Run example tests
        print("=" * 60)
        print("TESTING STANDALONE MESSAGES")
        print("=" * 60)
        
        examples = [
            "Queue is about 2h right now",
            "Just got in after 90 minutes wait",
            "No queue, walked straight in!",
            "Massive queue today, goes all the way to Wriezener",
            "Queue to the kiosk, maybe 45 min",
            "Got rejected after 3h wait 😭",
            "Short line, moved fast, inside now!",
        ]
        
        for example in examples:
            test_message(example)
        
        print("\n" + "=" * 60)
        print("TESTING CONTEXT-AWARE PARSING (Question → Answer)")
        print("=" * 60)
        
        # Context-aware examples: (parent, reply)
        context_examples = [
            ("How is the Q?", "To the kiosk"),
            ("How long is the queue?", "About 2h"),
            ("Anyone inside? How is it?", "Yes, got in!"),
            ("Current status?", "Massive, goes to Wriezener"),
            ("Did you get in?", "No, rejected :("),
            ("Queue update?", "Short, moved fast"),
            ("Wie lang ist die Schlange?", "Späti"),
        ]
        
        for parent, reply in context_examples:
            test_message(reply, parent_text=parent)


if __name__ == "__main__":
    main()
