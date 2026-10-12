"""Per-area rate limits for the public endpoints.

Each area has its own scope, so a burst of feedback cannot use up a visitor's chat budget.
Counts are kept in Django's cache (per process by default). Behind Caddy, set
NINJA_NUM_PROXIES=1 so limits count the real client address.

Django Ninja documents throttling as quota protection, not a security measure: IPs can be
spoofed. It protects free-tier LLM and speech API quotas.
"""

from django.conf import settings
from ninja.throttling import AnonRateThrottle


class ChatThrottle(AnonRateThrottle):
    scope = "chat"


class SpeechThrottle(AnonRateThrottle):
    scope = "speech"


class FeedbackThrottle(AnonRateThrottle):
    scope = "feedback"


CHAT_THROTTLE = ChatThrottle(settings.CHAT_RATE_LIMIT)
SPEECH_THROTTLE = SpeechThrottle(settings.SPEECH_RATE_LIMIT)
FEEDBACK_THROTTLE = FeedbackThrottle(settings.FEEDBACK_RATE_LIMIT)
