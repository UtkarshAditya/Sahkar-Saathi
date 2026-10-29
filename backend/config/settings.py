"""Django settings. Everything configurable comes from environment variables.

Local development reads ``backend/.env`` (copy ``.env.example``). Never commit ``.env``.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_value(name: str) -> str | None:
    """The variable's value, or None when it is unset or empty. Compose passes an empty
    string for `${NAME:-}`, which must mean "not set", not "false"."""
    value = os.environ.get(name)
    return value if value is not None and value.strip() else None


def env_bool(name: str, default: bool) -> bool:
    value = env_value(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def env_secret(name: str) -> str | None:
    """A secret from ``NAME``, or from the file named by ``NAME_FILE`` (Docker secrets)."""
    if value := os.environ.get(name):
        return value
    if (path := os.environ.get(f"{name}_FILE")) and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8").strip() or None
    return None


# --- Core -----------------------------------------------------------------------------

# "production" (set by docker-compose.yml) enforces real secrets and turns DEBUG off.
ENVIRONMENT = os.environ.get("DJANGO_ENV", "development")
PRODUCTION = ENVIRONMENT == "production"

DEBUG = False if PRODUCTION else env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env_secret("DJANGO_SECRET_KEY") or ""
if not SECRET_KEY:
    if PRODUCTION:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY or DJANGO_SECRET_KEY_FILE in production.")
    SECRET_KEY = "django-insecure-local-dev-only-change-me"  # `check --deploy` flags this

# localhost/127.0.0.1 are always allowed so the container health check works; only Caddy
# can reach the app, and Caddy only forwards requests for the configured site address.
ALLOWED_HOSTS = [*env_list("DJANGO_ALLOWED_HOSTS", "localhost"), "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",  # needed for the export_openapi_schema command
    "apps.chat",
    "apps.speech",
    "apps.feedback",
    "apps.knowledge",
    "apps.grievance",
    "apps.schemes",
    "apps.lessons",
    "apps.meta",
    "apps.evaluation",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# PostgreSQL in Compose (POSTGRES_HOST + POSTGRES_PASSWORD_FILE, or DATABASE_URL); SQLite
# when neither is set, for quick local runs. conn_max_age=0: persistent connections are not
# safe under ASGI.
if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=0)}
elif os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "sahkar"),
            "USER": os.environ.get("POSTGRES_USER", "sahkar"),
            "PASSWORD": env_secret("POSTGRES_PASSWORD") or "",
            "CONN_MAX_AGE": 0,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.parse(f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=0)
    }

# Rate-limit counters. "file" shares them across the uvicorn workers in one container
# (Compose); the default per-process memory cache is fine for one local process and tests.
# Not the database cache: Ninja checks throttles synchronously inside async views, and
# Django forbids synchronous database queries there.
if os.environ.get("CACHE_BACKEND") == "file":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": os.environ.get("CACHE_LOCATION", "/tmp/django_cache"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
# Filled by collectstatic; in Compose a volume shared with Caddy, which serves /static/.
STATIC_ROOT = Path(os.environ.get("STATIC_ROOT") or BASE_DIR / "staticfiles")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security ---------------------------------------------------------------------------

# Only Caddy can reach the app, and it sets X-Forwarded-Proto, so trust it behind the proxy.
if env_bool("TRUST_PROXY_HEADERS", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# DJANGO_HTTPS=true when the site is served over HTTPS (a real domain behind Caddy).
HTTPS = env_bool("DJANGO_HTTPS", False)
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SECURE_SSL_REDIRECT = HTTPS
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health$"]  # the in-container health check uses HTTP
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000")) if HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS
# Preload lists are hard to leave, so it is a deliberate opt-in (and the check is silenced
# only while it is off).
SECURE_HSTS_PRELOAD = HTTPS and env_bool("SECURE_HSTS_PRELOAD", False)
SILENCED_SYSTEM_CHECKS = [] if SECURE_HSTS_PRELOAD else ["security.W021"]
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # staff sessions last one working day

# Uploads: audio is checked by size in the speech endpoint; keep request bodies bounded.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440  # 2.5 MB of non-file form/JSON data
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440

# Behind Caddy, so rate limits see the real client address.
NINJA_NUM_PROXIES = (
    int(os.environ["NINJA_NUM_PROXIES"]) if os.environ.get("NINJA_NUM_PROXIES") else None
)

# --- Sahkar Saathi settings (shared with members B and C) -----------------------------

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

# Serve stub answers, retrieval and speech until the real services land. USE_STUBS is the
# default for every service; each USE_STUB_<SERVICE> flag overrides it for one service, so
# mixed mode works (for example a real answer service over the stub retriever).
USE_STUBS = env_bool("USE_STUBS", True)
USE_STUB_RETRIEVER = env_bool("USE_STUB_RETRIEVER", USE_STUBS)
USE_STUB_ANSWER = env_bool("USE_STUB_ANSWER", USE_STUBS)
USE_STUB_SPEECH = env_bool("USE_STUB_SPEECH", USE_STUBS)
USE_STUB_GRIEVANCE = env_bool("USE_STUB_GRIEVANCE", USE_STUBS)
# Serve the saved answers for the scripted demo questions (data/demo_answers.yaml), and use
# them as a fallback when a live service fails on one of those questions.
DEMO_CACHE = env_bool("DEMO_CACHE", False)
# Turn off to keep no message text at all (Sprint 2, when messages are stored).
STORE_MESSAGES = env_bool("STORE_MESSAGES", True)

REGIONAL_LANGUAGE_CODE = os.environ.get("REGIONAL_LANGUAGE_CODE", "ta")
REGIONAL_LANGUAGE_LABEL = os.environ.get("REGIONAL_LANGUAGE_LABEL", "தமிழ்")
REGIONAL_LANGUAGE_ENGLISH_NAME = os.environ.get("REGIONAL_LANGUAGE_ENGLISH_NAME", "Tamil")
# The one state whose Act and rules are in the knowledge base (team decision).
COVERED_STATE_CODE = os.environ.get("COVERED_STATE_CODE", "TN")
# Structured content with sources: schemes.yaml, lessons.yaml (and later forums.yaml).
CONTENT_DIR = Path(os.environ.get("CONTENT_DIR") or BASE_DIR / "data")
SUPPORTED_LANGUAGES = ["en", "hi", REGIONAL_LANGUAGE_CODE]

# Agent and language model (member C). services/llm.py reads LLM_BASE_URL, LLM_MODEL,
# LLM_API_KEY, LLM_TIMEOUT and LLM_JSON_MODE itself, at call time. LLM_PROVIDER is a label
# only; nothing reads it yet.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
# Who a declined answer tells the user to contact. Never put an unverified number here.
HELPLINE_LABEL = (
    env_value("HELPLINE_LABEL")
    or "Your district cooperative office (Registrar of Co-operative Societies)"
)
HELPLINE_DETAIL = (
    env_value("HELPLINE_DETAIL") or "Verified helpline numbers will be added from forums.yaml."
)
BHASHINI_API_KEY = os.environ.get("BHASHINI_API_KEY", "")
BHASHINI_USER_ID = os.environ.get("BHASHINI_USER_ID", "")

# Chunking configuration (member B)
CHUNK_MAX_CHARS = int(os.environ.get("CHUNK_MAX_CHARS", "900"))
CHUNK_MIN_CHARS = int(os.environ.get("CHUNK_MIN_CHARS", "80"))
CHUNK_TAIL_MERGE_CHARS = int(os.environ.get("CHUNK_TAIL_MERGE_CHARS", "150"))

# Retrieval (member B). Recorded in every evaluation run.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
TOP_K = int(os.environ.get("TOP_K", "4"))
SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.5"))
SCORE_THRESHOLD_BY_LANG = {
    "en": float(os.environ.get("SCORE_THRESHOLD_EN", str(SCORE_THRESHOLD))),
    "hi": float(os.environ.get("SCORE_THRESHOLD_HI", str(SCORE_THRESHOLD))),
    "ta": float(os.environ.get("SCORE_THRESHOLD_TA", str(SCORE_THRESHOLD))),
}
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
HEALTH_CHECK_TIMEOUT_SECONDS = float(os.environ.get("HEALTH_CHECK_TIMEOUT_SECONDS", "1.5"))

# Request limits.
# Rate limits per client address, as "<count>/<s|m|h|d>". Each area has its own budget.
CHAT_RATE_LIMIT = os.environ.get("CHAT_RATE_LIMIT") or "20/m"
SPEECH_RATE_LIMIT = os.environ.get("SPEECH_RATE_LIMIT") or "20/m"
FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT") or "30/m"
GRIEVANCE_RATE_LIMIT = os.environ.get("GRIEVANCE_RATE_LIMIT") or "10/m"
CHAT_MAX_QUESTION_CHARS = int(os.environ.get("CHAT_MAX_QUESTION_CHARS", "1000"))
SPEECH_MAX_UPLOAD_BYTES = int(os.environ.get("SPEECH_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
SPEECH_MAX_SYNTH_CHARS = int(os.environ.get("SPEECH_MAX_SYNTH_CHARS", "2000"))
SPEECH_ALLOWED_CONTENT_TYPES = [
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
]

# --- Logging: status and latency only, never message text -----------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "sahkar": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
        # Unhandled errors and security events (bad Host headers, CSRF failures) must reach
        # the container logs; Django only mails them by default when DEBUG is off.
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
