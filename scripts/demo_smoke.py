#!/usr/bin/env python3
"""Demo-day smoke test: every screen's endpoint, in the order a demo uses them, as a table.

    python scripts/demo_smoke.py [BASE_URL] [--file data/eval/conversations.json]
                                 [--staff-user NAME] [--api-only]

BASE_URL defaults to http://localhost (docker compose). Checks, each marked PASS or FAIL:
the front end, /health, /meta/languages, /meta/states, the five scripted conversations
through /chat/ask (expectations in data/eval/conversations.json), /feedback, /grievance/guide,
/schemes, /lessons, /documents and /eval/latest. Exits 1 if anything fails.

/eval/latest is staff only. Give a staff login to check the data itself:

    DEMO_STAFF_USER=admin DEMO_STAFF_PASSWORD=... python scripts/demo_smoke.py

(the password is read from the environment so it never appears in a command line or in the
shell history; the admin password is shown by `docker compose exec web cat
/secrets/admin_password`). Without a login the script checks that anonymous access is refused.

For the scripted conversations to pass on the stubs, run the stack with DEMO_CACHE=true.
Against an https:// address it also checks the HSTS header and the Secure cookie flag.
Standard library only, so it runs anywhere Python 3.10+ is installed.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_FILE = HERE.parent / "data" / "eval" / "conversations.json"
TIMEOUT_SECONDS = 30


class Failure(Exception):
    """Raised by a check to say why it failed."""


@dataclass
class Result:
    name: str
    ok: bool
    millis: int
    detail: str


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    """A tiny HTTP client with a cookie jar, so a staff login carries over to later calls."""

    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            NoRedirect, urllib.request.HTTPCookieProcessor(self.jar)
        )

    def raw(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> tuple[int, dict[str, str], bytes]:
        request = urllib.request.Request(
            f"{self.base}{path}", data=data, method=method, headers=headers or {}
        )
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as err:
            return err.code, dict(err.headers), err.read()
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise Failure(f"no response: {getattr(err, 'reason', err)}") from err

    def api(self, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        status, response_headers, raw = self.raw(
            method, f"/api/v1{path}", data=payload, headers=headers
        )
        if "json" in response_headers.get("Content-Type", "") and raw:
            return status, json.loads(raw)
        return status, None


# --- The checks -----------------------------------------------------------------------


def expect(condition: object, message: str) -> None:
    if not condition:
        raise Failure(message)


def get_ok(client: Client, path: str) -> object:
    status, body = client.api("GET", path)
    expect(status == 200, f"HTTP {status}")
    return body


def check_frontend(client: Client) -> str:
    status, _, body = client.raw("GET", "/")
    expect(status == 200, f"HTTP {status}")
    expect(b'id="root"' in body, "the React app's root element is missing")
    return "React app served"


def check_health(client: Client) -> str:
    health = get_ok(client, "/health")
    detail = (
        f"stubs={health['stubs']}, database={health['database']}, "
        f"vector_store={health['vector_store']}"
    )
    expect(health["status"] == "ok", f"status {health['status']!r} ({detail})")
    return detail


def check_languages(client: Client) -> str:
    codes = [lang["code"] for lang in get_ok(client, "/meta/languages")]
    expect({"en", "hi"} <= set(codes) and len(codes) == 3, f"languages are {codes}")
    return ", ".join(codes)


def check_states(client: Client) -> str:
    covered = [s["code"] for s in get_ok(client, "/meta/states") if s["covered"]]
    expect(len(covered) == 1, f"covered states: {covered}")
    return f"covered: {covered[0]}"


def check_feedback(client: Client, message_id: str | None) -> str:
    expect(message_id, "no answer was received to rate")
    status, _ = client.api("POST", "/feedback", {"message_id": message_id, "rating": "up"})
    expect(status == 201, f"HTTP {status}")
    return "rating stored"


def check_grievance(client: Client) -> str:
    status, body = client.api(
        "POST",
        "/grievance/guide",
        {
            "description": "My society has not refunded my deposit after two written requests.",
            "language": "en",
        },
    )
    expect(status == 200, f"HTTP {status}")
    for key in ("category", "forum", "forum_note", "steps", "documents_needed", "draft_text"):
        expect(body.get(key), f"{key} is empty")
    return (
        f"category {body['category']['id']}, {len(body['steps'])} steps, is_demo={body['is_demo']}"
    )


def check_schemes(client: Client) -> str:
    schemes = get_ok(client, "/schemes")
    expect(schemes, "no schemes")
    pmfby = get_ok(client, "/schemes/pmfby")
    expect(pmfby["facts"], "the PMFBY guide has no facts")
    return f"{len(schemes)} schemes, PMFBY guide has {len(pmfby['facts'])} facts"


def check_lessons(client: Client) -> str:
    lessons = get_ok(client, "/lessons")
    expect(lessons["lessons"] and lessons["quiz"], "no lessons or no quiz")
    return f"{len(lessons['lessons'])} lessons, {len(lessons['quiz'])} quiz questions"


def check_documents(client: Client) -> str:
    documents = get_ok(client, "/documents")
    expect(documents, "the library is empty")
    return f"{len(documents)} active documents"


def staff_login(client: Client, user: str, password: str) -> None:
    """Log in through the admin login page, which sets the session cookie the API checks."""
    status, _, page = client.raw("GET", "/admin/login/")
    match = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    expect(status == 200 and match, f"the admin login page did not load (HTTP {status})")
    form = urllib.parse.urlencode(
        {
            "username": user,
            "password": password,
            "csrfmiddlewaretoken": match.group(1).decode(),
            "next": "/admin/",
        }
    ).encode()
    status, _, _ = client.raw(
        "POST",
        "/admin/login/",
        data=form,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": f"{client.base}/admin/login/",
        },
    )
    expect(status == 302, "the staff login was refused (wrong user or password?)")


def check_eval(client: Client, staff: tuple[str, str] | None) -> str:
    if staff is None:
        status, body = client.api("GET", "/eval/latest")
        expect(status == 401, f"anonymous access gave HTTP {status}, expected 401")
        expect(body and body.get("code") == "not_authenticated", "unexpected error body")
        return "401 for anonymous, as intended (set DEMO_STAFF_* to check the data)"
    staff_login(client, *staff)
    summary = get_ok(client, "/eval/latest")
    expect(len(summary["metrics"]) == 3, "expected three metrics")
    kind = "SAMPLE numbers" if summary["is_sample"] else "recorded run"
    return f"{kind}: {summary['latest']['label']}"


def check_https(client: Client) -> str:
    _, headers, _ = client.raw("GET", "/api/v1/health")
    expect("max-age" in headers.get("Strict-Transport-Security", ""), "no HSTS header")
    client.raw("GET", "/admin/login/")
    cookies = {c.name: c for c in client.jar}
    expect("csrftoken" in cookies, "no CSRF cookie was set")
    expect(cookies["csrftoken"].secure, "the CSRF cookie is not marked Secure")
    return "HSTS header present, cookies are Secure"


# --- Running them ---------------------------------------------------------------------


def timed(name: str, check: Callable[[], str]) -> Result:
    started = time.perf_counter()
    try:
        detail, ok = check(), True
    except Failure as err:
        detail, ok = str(err), False
    except Exception as err:  # a malformed response must fail the check, not the script
        detail, ok = f"{err.__class__.__name__}: {err}", False
    return Result(name, ok, int((time.perf_counter() - started) * 1000), detail)


def load_acceptance():
    """The scripted-conversation helpers live in scripts/acceptance.py."""
    sys.path.insert(0, str(HERE))
    import acceptance

    return acceptance


def conversation_checks(
    client: Client, conversations: list[dict], acceptance, found: dict
) -> list[tuple[str, Callable[[], str]]]:
    checks = []
    for conversation in conversations:
        state = {"conversation_id": None}
        for number, turn in enumerate(conversation["turns"], start=1):

            def run(turn=turn, state=state):
                payload = {"text": turn["text"], "language": turn.get("language", "en")}
                if turn.get("state"):
                    payload["state"] = turn["state"]
                if state["conversation_id"]:
                    payload["conversation_id"] = state["conversation_id"]
                status, body = acceptance.ask(client.base, payload)
                state["conversation_id"] = body.get("conversation_id") or state["conversation_id"]
                problems = acceptance.check_turn(turn, status, body)
                if problems:
                    raise Failure("; ".join(problems))
                found.setdefault("message_id", body.get("message_id"))
                # A PASS on a saved or stub answer must not read as a live-pipeline check;
                # scripts/acceptance.py (DEMO_CACHE=false) is the live check.
                kind = " [demo answer, not live]" if body.get("is_demo") else ""
                return f"{body['status']}, {len(body.get('citations') or [])} citation(s){kind}"

            language = turn.get("language", "en")
            label = f"POST /chat/ask · {conversation['id']} #{number} [{language}]"
            checks.append((label, run))
    return checks


def print_table(results: list[Result]) -> None:
    width = max(len(r.name) for r in results)
    print(f"\n{'RESULT':<6}  {'CHECK':<{width}}  {'TIME':>7}  DETAIL")
    print(f"{'-' * 6}  {'-' * width}  {'-' * 7}  {'-' * 40}")
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"{mark:<6}  {r.name:<{width}}  {r.millis:>5} ms  {r.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test every demo endpoint.")
    parser.add_argument("base_url", nargs="?", default="http://localhost")
    parser.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    parser.add_argument(
        "--staff-user",
        default=os.environ.get("DEMO_STAFF_USER"),
        help="Staff user for /eval/latest (the password comes from DEMO_STAFF_PASSWORD).",
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Skip the front-end check, for a bare backend (uvicorn) with no web server in front.",
    )
    args = parser.parse_args(argv)

    password = os.environ.get("DEMO_STAFF_PASSWORD")
    staff = (args.staff_user, password) if args.staff_user and password else None
    if bool(args.staff_user) != bool(password):
        print("Note: both a staff user and DEMO_STAFF_PASSWORD are needed to log in; skipping it.")

    acceptance = load_acceptance()
    conversations = acceptance.load_conversations(args.file)
    client = Client(args.base_url)
    found: dict = {}

    checks: list[tuple[str, Callable[[], str]]] = [
        *([] if args.api_only else [("Front end served", lambda: check_frontend(client))]),
        ("GET /health", lambda: check_health(client)),
        ("GET /meta/languages", lambda: check_languages(client)),
        ("GET /meta/states", lambda: check_states(client)),
        *conversation_checks(client, conversations, acceptance, found),
        ("POST /feedback", lambda: check_feedback(client, found.get("message_id"))),
        ("POST /grievance/guide", lambda: check_grievance(client)),
        ("GET /schemes", lambda: check_schemes(client)),
        ("GET /lessons", lambda: check_lessons(client)),
        ("GET /documents", lambda: check_documents(client)),
        ("GET /eval/latest", lambda: check_eval(client, staff)),
    ]
    if args.base_url.lower().startswith("https://"):
        checks.append(("HTTPS: HSTS and Secure cookies", lambda: check_https(client)))

    print(f"Demo smoke test against {args.base_url}")
    results = [timed(name, check) for name, check in checks]
    print_table(results)
    failed = [r for r in results if not r.ok]
    print(f"\n{len(results)} checks: {len(results) - len(failed)} passed, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
