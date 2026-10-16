"""Production configuration: the management commands the container runs on start, and
Django's own deployment checklist (`manage.py check --deploy`)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.knowledge.models import Document

BACKEND = Path(__file__).resolve().parent.parent


def test_ensure_superuser_creates_once_and_never_resets(monkeypatch):
    User = get_user_model()
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "teamadmin")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "first-Password-123")
    call_command("ensure_superuser")
    user = User.objects.get(username="teamadmin")
    assert user.is_superuser and user.is_staff

    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "second-Password-456")
    call_command("ensure_superuser")
    user.refresh_from_db()
    assert user.check_password("first-Password-123"), "an existing password must not change"


def test_ensure_superuser_reads_password_file(monkeypatch, tmp_path):
    secret = tmp_path / "admin_password"
    secret.write_text("from-a-File-789\n", encoding="utf-8")
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "fileadmin")
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD_FILE", str(secret))
    call_command("ensure_superuser")
    assert get_user_model().objects.get(username="fileadmin").check_password("from-a-File-789")


def test_ensure_superuser_skips_without_password(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD_FILE", raising=False)
    call_command("ensure_superuser")
    assert not get_user_model().objects.exists()


def test_sample_documents_load_only_into_an_empty_table():
    call_command("load_sample_documents")
    assert Document.objects.count() == 9

    Document.objects.filter(pk="doc-tn-act").update(title="Edited in the admin")
    call_command("load_sample_documents")
    assert Document.objects.get(pk="doc-tn-act").title == "Edited in the admin"


def _manage(*args: str, **env: str) -> subprocess.CompletedProcess:
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "POSTGRES_"))}
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=BACKEND,
        env={**clean, "DJANGO_SETTINGS_MODULE": "config.settings", **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


PRODUCTION = {
    "DJANGO_ENV": "production",
    "DJANGO_SECRET_KEY": "x" * 30 + "-a-long-random-test-secret-key-0123456789",
    "DJANGO_ALLOWED_HOSTS": "demo.example.org",
    "TRUST_PROXY_HEADERS": "true",
}


@pytest.mark.django_db(transaction=False)
def test_production_https_passes_the_deployment_checklist():
    result = _manage(
        "check", "--deploy", "--fail-level", "WARNING", **PRODUCTION, DJANGO_HTTPS="true"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout


def test_production_refuses_to_start_without_a_secret_key():
    env = {k: v for k, v in PRODUCTION.items() if k != "DJANGO_SECRET_KEY"}
    result = _manage("check", **env)
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY" in result.stderr


def test_production_forces_debug_off():
    result = _manage(
        "shell",
        "-c",
        "from django.conf import settings; print(settings.DEBUG)",
        **PRODUCTION,
        DJANGO_DEBUG="true",
    )
    assert result.stdout.strip().endswith("False"), result.stdout + result.stderr


def test_async_endpoints_work_with_the_production_cache(client, settings, tmp_path):
    """Regression: throttles run synchronously inside async views, so the cache backend used
    in Compose must not query the database (the database cache raised a 500 there)."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": str(tmp_path / "cache"),
        }
    }
    res = client.post(
        "/api/v1/chat/ask", data='{"text": "PMFBY claim"}', content_type="application/json"
    )
    assert res.status_code == 200, res.content
