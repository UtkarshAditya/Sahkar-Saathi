"""Django settings. Everything configurable comes from environment variables.

Local development reads ``backend/.env`` (copy ``.env.example``). Never commit ``.env``.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core -----------------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", False)
# The fallback key is only for local development; `manage.py check --deploy` flags it.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "django-insecure-local-dev-only-change-me"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
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

# PostgreSQL in Compose (DATABASE_URL=postgres://...); SQLite when unset, for quick local runs.
# conn_max_age=0: persistent connections are not safe under ASGI.
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0,
    )
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
STATIC_ROOT = BASE_DIR / "staticfiles"  # filled by collectstatic, served by Caddy
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Behind Caddy, so rate limits see the real client address.
NINJA_NUM_PROXIES = (
    int(os.environ["NINJA_NUM_PROXIES"]) if os.environ.get("NINJA_NUM_PROXIES") else None
)

# --- Sahkar Saathi settings (shared with members B and C) -----------------------------

APP_VERSION = os.environ.get("APP_VERSION", "0.1.0")

# Serve stub answers, retrieval and speech until the real services land.
USE_STUBS = env_bool("USE_STUBS", True)
# Serve saved answers for the five scripted conversations if a service is down (Sprint 3).
DEMO_CACHE = env_bool("DEMO_CACHE", False)
# Turn off to keep no message text at all (Sprint 2, when messages are stored).
STORE_MESSAGES = env_bool("STORE_MESSAGES", True)

REGIONAL_LANGUAGE_CODE = os.environ.get("REGIONAL_LANGUAGE_CODE", "ta")
SUPPORTED_LANGUAGES = ["en", "hi", REGIONAL_LANGUAGE_CODE]

# Agent and language model (member C).
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
BHASHINI_API_KEY = os.environ.get("BHASHINI_API_KEY", "")
BHASHINI_USER_ID = os.environ.get("BHASHINI_USER_ID", "")

# Retrieval (member B). Recorded in every evaluation run.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
TOP_K = int(os.environ.get("TOP_K", "4"))
SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.5"))
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")

# Request limits.
# Rate limits per client address, as "<count>/<s|m|h|d>". Each area has its own budget.
CHAT_RATE_LIMIT = os.environ.get("CHAT_RATE_LIMIT") or "20/m"
SPEECH_RATE_LIMIT = os.environ.get("SPEECH_RATE_LIMIT") or "20/m"
FEEDBACK_RATE_LIMIT = os.environ.get("FEEDBACK_RATE_LIMIT") or "30/m"
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
    },
}
