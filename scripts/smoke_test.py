#!/usr/bin/env python3
"""Smoke test for a running stack, seen from outside (the way a browser sees it).

    python scripts/smoke_test.py                       # http://localhost (docker compose)
    python scripts/smoke_test.py https://demo.example.org

Checks the React app, every public API area, the admin site, security headers, and that
the internal services (Django, PostgreSQL, Qdrant) are not reachable directly. Standard
library only, so it runs anywhere Python 3.10+ is installed. Exits 1 if anything fails.
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost").rstrip("/")
API = f"{BASE}/api/v1"
failures: list[str] = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def request(method: str, url: str, body: bytes | None = None, headers: dict | None = None):
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with OPENER.open(req, timeout=15) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read()


def get_json(path: str):
    status, headers, body = request("GET", f"{API}{path}")
    return status, json.loads(body) if body and "json" in headers.get("Content-Type", "") else None


def post_json(path: str, payload: dict):
    status, headers, body = request(
        "POST", f"{API}{path}", json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    return status, json.loads(body) if "json" in headers.get("Content-Type", "") else body


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{f'  ({detail})' if detail and not ok else ''}")
    if not ok:
        failures.append(name)


def multipart(field: str, filename: str, content_type: str, data: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return body, f"multipart/form-data; boundary={boundary}"


def main() -> int:
    print(f"Smoke test against {BASE}\n")

    # --- Front end ---
    status, headers, body = request("GET", f"{BASE}/")
    check("React app is served", status == 200 and b'id="root"' in body, f"status {status}")
    check(
        "CSP header on the app", "default-src 'self'" in headers.get("Content-Security-Policy", "")
    )
    check("nosniff header", headers.get("X-Content-Type-Options") == "nosniff")
    check("no Server header", "Server" not in headers, headers.get("Server", ""))
    status, _, body = request("GET", f"{BASE}/library")
    check("deep links fall back to index.html", status == 200 and b'id="root"' in body)

    # --- API ---
    status, health = get_json("/health")
    check("GET /health is ok", status == 200 and health and health["status"] == "ok", str(health))
    check("database reachable", bool(health) and health.get("database") == "ok")

    status, langs = get_json("/meta/languages")
    check("GET /meta/languages", status == 200 and len(langs or []) == 3)
    status, states = get_json("/meta/states")
    check("GET /meta/states marks one covered state", sum(s["covered"] for s in states or []) == 1)

    status, answer = post_json(
        "/chat/ask", {"text": "What should I do if my insured crop is damaged under PMFBY?"}
    )
    ok = status == 200 and answer["status"] == "answered" and answer["citations"]
    check("POST /chat/ask answers with citations", bool(ok), f"status {status}")
    if ok:
        status, _fb = post_json("/feedback", {"message_id": answer["message_id"], "rating": "up"})
        check("POST /feedback stores a rating", status == 201, f"status {status}")

    status, declined = post_json("/chat/ask", {"text": "asdf"})
    check("declined answers name a contact", status == 200 and declined["contact"] is not None)

    status, error = post_json("/chat/ask", {"text": ""})
    check(
        "errors use the {code, message} shape", status == 422 and set(error) == {"code", "message"}
    )

    status, docs = get_json("/documents")
    check("GET /documents", status == 200 and isinstance(docs, list), f"status {status}")
    status, pmfby = get_json("/schemes/pmfby")
    check("GET /schemes/pmfby has guide facts", status == 200 and len(pmfby["facts"]) >= 1)
    status, lessons = get_json("/lessons")
    check("GET /lessons has a quiz", status == 200 and len(lessons["quiz"]) == 3)
    status, guide = post_json(
        "/grievance/guide",
        {
            "description": "My society has not refunded my deposit after two requests.",
            "language": "en",
        },
    )
    check("POST /grievance/guide drafts a complaint", status == 200 and guide["draft_text"])

    status, headers, audio = request(
        "POST",
        f"{API}/speech/synthesize",
        json.dumps({"text": "Report the loss early.", "language": "en"}).encode(),
        {"Content-Type": "application/json"},
    )
    check("POST /speech/synthesize returns WAV", status == 200 and audio[:4] == b"RIFF")
    body, ctype = multipart("audio", "q.webm", "audio/webm", b"\x1a\x45\xdf\xa3" + b"\0" * 2000)
    status, _, raw = request("POST", f"{API}/speech/transcribe", body, {"Content-Type": ctype})
    check("POST /speech/transcribe returns text", status == 200 and b'"text"' in raw, f"{status}")

    status, _ = get_json("/eval/latest")
    check("GET /eval/latest is staff only (401)", status == 401, f"status {status}")

    # --- Admin and static files ---
    status, _, body = request("GET", f"{BASE}/admin/login/")
    check("admin login page", status == 200 and b"csrfmiddlewaretoken" in body, f"status {status}")
    status, _, _ = request("GET", f"{BASE}/static/admin/css/base.css")
    check("admin static files served by Caddy", status == 200, f"status {status}")
    status, headers, _ = request("GET", f"{API}/docs")
    check(
        "API docs are staff only", status == 302 and "/admin/login" in headers.get("Location", "")
    )

    # --- Internal services must not be published ---
    host = urlparse(BASE).hostname or "localhost"
    if host in {"localhost", "127.0.0.1"}:
        for port, name in [(8000, "Django"), (5432, "PostgreSQL"), (6333, "Qdrant")]:
            with socket.socket() as s:
                s.settimeout(1)
                closed = s.connect_ex(("127.0.0.1", port)) != 0
            check(f"{name} port {port} is not published", closed)

    print(f"\n{'All checks passed.' if not failures else f'{len(failures)} check(s) failed.'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
