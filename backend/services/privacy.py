"""Remove personal identifiers from text before it is stored. Plain Python, no Django.

The public service stores no names, phone numbers or ID numbers (architecture doc,
section 4). This is a conservative baseline scrub; member C's safety module can replace
or extend it. It runs on question, answer and feedback text before any database write.
"""

import re

# Order matters: specific patterns first, then the generic long-number catch-all.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    # Aadhaar: 12 digits, often grouped 4-4-4.
    (re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)"), "[aadhaar]"),
    # Indian mobile numbers, optionally with +91 / 91 / 0 prefix and a space or dash.
    (re.compile(r"(?<!\d)(?:\+?91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"), "[phone]"),
    # PAN: five letters, four digits, one letter.
    (re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b"), "[pan]"),
    # Bank account, membership or other long ID numbers.
    (re.compile(r"(?<!\d)\d{9,18}(?!\d)"), "[number]"),
]


def scrub_pii(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
