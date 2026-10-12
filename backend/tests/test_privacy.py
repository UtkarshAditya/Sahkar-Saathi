import pytest

from services.privacy import scrub_pii


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("call 9876543210", "call [phone]"),
        ("call +91 98765 43210", "call [phone]"),
        ("call 09876543210", "call [phone]"),
        ("aadhaar 1234-5678-9012", "aadhaar [aadhaar]"),
        ("mail ravi.k@example.co.in", "mail [email]"),
        ("PAN ABCDE1234F", "PAN [pan]"),
        ("account 001234567890123", "account [number]"),
    ],
)
def test_identifiers_are_removed(text, expected):
    assert scrub_pii(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Section 32 of the 1983 Act",
        "Premium of ₹1,500 for 2 hectares",
        "Kharif 2026, page 34",
    ],
)
def test_ordinary_numbers_are_kept(text):
    assert scrub_pii(text) == text
