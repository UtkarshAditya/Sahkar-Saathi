"""scripts/demo_smoke.py against a real HTTP server (pytest-django's live_server), with the
demo cache on so the scripted conversations pass on the stubs. No network, no model.

The live server is bare Django, with no web server in front, so most runs use --api-only.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "demo_smoke.py"
PASSWORD = "pw-for-tests"


def load_script():
    spec = importlib.util.spec_from_file_location("demo_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_smoke"] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


def address(live_server) -> str:
    # 127.0.0.1, not localhost: on Windows "localhost" tries IPv6 first, about 2 s per request.
    return live_server.url.replace("localhost", "127.0.0.1")


@pytest.fixture(autouse=True)
def no_staff_login(monkeypatch):
    monkeypatch.delenv("DEMO_STAFF_USER", raising=False)
    monkeypatch.delenv("DEMO_STAFF_PASSWORD", raising=False)


@pytest.fixture
def demo(settings, live_server):
    settings.DEMO_CACHE = True
    call_command("load_sample_documents")
    return address(live_server)


def run(url, capsys, *args, api_only=True):
    options = [*args, "--api-only"] if api_only else list(args)
    code = load_script().main([url, *options])
    return code, capsys.readouterr().out


def rows(out: str) -> dict[str, str]:
    """{check name: PASS or FAIL}, read from the printed table."""
    found = {}
    for line in out.splitlines():
        if line.startswith(("PASS", "FAIL")):
            mark, rest = line[:4], line[4:].strip()
            found[rest.split("  ")[0].strip()] = mark
    return found


def test_everything_passes_and_the_table_lists_every_screen(demo, capsys):
    code, out = run(demo, capsys)
    assert code == 0, out
    table = rows(out)
    for name in (
        "GET /health",
        "GET /meta/languages",
        "GET /meta/states",
        "POST /feedback",
        "POST /grievance/guide",
        "GET /schemes",
        "GET /lessons",
        "GET /documents",
        "GET /eval/latest",
    ):
        assert table.get(name) == "PASS", (name, out)
    chat = [name for name in table if name.startswith("POST /chat/ask")]
    assert len(chat) == 6, "five conversations, six turns"
    assert "RESULT" in out and "TIME" in out and "DETAIL" in out
    assert "checks:" in out and "0 failed." in out
    assert out.count("[demo answer, not live]") == 6, "cached answers are labelled as such"


def test_the_front_end_check_fails_when_nothing_serves_the_app(demo, capsys):
    """Bare Django has no React app at /, so the front-end check reports it."""
    code, out = run(demo, capsys, api_only=False)
    table = rows(out)
    assert code == 1 and table["Front end served"] == "FAIL" and "HTTP 404" in out
    assert [name for name, mark in table.items() if mark == "FAIL"] == ["Front end served"]


def test_api_only_skips_the_front_end_check(demo, capsys):
    _, out = run(demo, capsys)
    assert "Front end served" not in out


def test_anonymous_access_to_the_dashboard_is_checked_to_be_refused(demo, capsys):
    _, out = run(demo, capsys)
    assert "401 for anonymous, as intended" in out


def test_a_staff_login_checks_the_dashboard_data(demo, capsys, monkeypatch):
    get_user_model().objects.create_user("staff", password=PASSWORD, is_staff=True)
    monkeypatch.setenv("DEMO_STAFF_USER", "staff")
    monkeypatch.setenv("DEMO_STAFF_PASSWORD", PASSWORD)
    code, out = run(demo, capsys)
    assert code == 0, out
    assert "SAMPLE numbers" in out, "no run is recorded, so the sample data is served"


def test_a_wrong_staff_password_fails_that_check_only(demo, capsys, monkeypatch):
    get_user_model().objects.create_user("staff", password=PASSWORD, is_staff=True)
    monkeypatch.setenv("DEMO_STAFF_USER", "staff")
    monkeypatch.setenv("DEMO_STAFF_PASSWORD", "wrong-password")
    code, out = run(demo, capsys)
    table = rows(out)
    assert code == 1 and "refused" in out
    assert [name for name, mark in table.items() if mark == "FAIL"] == ["GET /eval/latest"]


def test_the_password_is_never_printed(demo, capsys, monkeypatch):
    get_user_model().objects.create_user("staff", password=PASSWORD, is_staff=True)
    monkeypatch.setenv("DEMO_STAFF_USER", "staff")
    monkeypatch.setenv("DEMO_STAFF_PASSWORD", PASSWORD)
    _, out = run(demo, capsys)
    assert PASSWORD not in out


def test_a_user_without_a_password_is_told_it_is_skipped(demo, capsys, monkeypatch):
    monkeypatch.setenv("DEMO_STAFF_USER", "staff")
    _, out = run(demo, capsys)
    assert "both a staff user and DEMO_STAFF_PASSWORD are needed" in out


def test_without_the_demo_cache_the_scripted_72_hour_answer_fails_on_the_stub(
    settings, live_server, capsys
):
    """The stub answer does not quote the deadline, which is what DEMO_CACHE is for."""
    settings.DEMO_CACHE = False
    code, out = run(address(live_server), capsys)
    assert code == 1
    assert rows(out)["POST /chat/ask · pmfby-loss-en #1 [en]"] == "FAIL"
    assert "does not contain '72'" in out


def test_an_unreachable_server_fails_every_check_with_a_reason(capsys):
    code, out = run("http://127.0.0.1:1", capsys)
    table = rows(out)
    assert code == 1 and table and set(table.values()) == {"FAIL"}
    assert "no response" in out.lower()


def test_one_failing_check_does_not_stop_the_run(demo, capsys, monkeypatch):
    module = load_script()

    def broken(client):
        raise KeyError("lessons")

    monkeypatch.setattr(module, "check_lessons", broken)
    code = module.main([demo, "--api-only"])
    table = rows(capsys.readouterr().out)
    assert code == 1 and table["GET /lessons"] == "FAIL" and table["GET /documents"] == "PASS"
