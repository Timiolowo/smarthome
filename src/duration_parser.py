"""
Natural Language Duration and Number Parser.
Converts spoken English duration expressions (e.g., 'the next two minutes',
'half an hour', '15 mins', 'an hour', 'three seconds') into exact seconds.
"""

import re
from typing import Optional

WORD_TO_NUMBER = {
    "zero": 0, "a": 1, "an": 1, "one": 1, "two": 2, "couple": 2, "three": 3, "few": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90,
}


def parse_spoken_number(text: str) -> Optional[float]:
    """Parses digits or number words (e.g. '2', '2.5', 'two', 'twenty five') into a float."""
    clean = text.strip().lower().replace("-", " ")
    # Check digits first
    try:
        return float(clean)
    except ValueError:
        pass

    # Check known compounds like "twenty five"
    words = clean.split()
    total = 0.0
    matched = False
    for w in words:
        if w in WORD_TO_NUMBER:
            val = WORD_TO_NUMBER[w]
            total += val
            matched = True
        elif w == "and":
            continue
        elif w == "half":
            total += 0.5
            matched = True

    return total if matched and total > 0 else None


def extract_duration_seconds(text: str) -> Optional[float]:
    """
    Extracts duration in seconds from any natural phrasing in the text.
    Examples:
    - 'the next two minutes' -> 120.0
    - '2 minutes' -> 120.0
    - 'half an hour' -> 1800.0
    - 'an hour' -> 3600.0
    - '45 seconds' -> 45.0
    - 'a couple of minutes' -> 120.0
    - '1.5 hours' -> 5400.0
    """
    clean = text.lower().strip()

    # Special idioms
    if "half an hour" in clean or "half hour" in clean:
        return 1800.0
    if "an hour" in clean or "one hour" in clean:
        return 3600.0
    if "a minute" in clean or "one minute" in clean:
        return 60.0

    # Pattern matching: (optional "the next" / "about" / "like") + (number or word) + (unit: sec/min/hour)
    match = re.search(
        r"(?:for\s+|in\s+)?(?:the\s+next\s+|about\s+|around\s+|like\s+)?([a-zA-Z0-9_.\s-]+?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
        clean,
        re.IGNORECASE,
    )
    if match:
        num_str = match.group(1).strip()
        unit_str = match.group(2).lower()

        # Extract number portion
        # If num_str has leading filler, take the last 1-2 words
        words = num_str.split()
        cand = words[-2:] if len(words) >= 2 else words
        num = parse_spoken_number(" ".join(cand))
        if num is None:
            num = parse_spoken_number(words[-1]) if words else None

        if num is not None and num > 0:
            if "sec" in unit_str:
                return float(num)
            elif "hour" in unit_str or "hr" in unit_str:
                return float(num * 3600)
            else:
                return float(num * 60)

    return None
