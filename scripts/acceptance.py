#!/usr/bin/env python3
"""Acceptance run for the chat pipeline, seen from outside the way a browser sees it.

    python scripts/acceptance.py [BASE_URL] [--file data/eval/conversations.json]
                                 [--allow-demo]

BASE_URL defaults to http://localhost (docker compose). Each conversation in the file is
asked turn by turn through POST /api/v1/chat/ask; follow-up turns reuse the returned
conversation_id. The file format is described in data/eval/README.md.

Checked on every turn, whatever the file says:
- a declined answer has no citations and carries a contact;
- an answered one has at least one citation;
- the response says whether it is a demo answer (is_demo).
Checked when the turn lists it: status, citations (true/false), must_contain (case-
insensitive), expect_doc_ids (at least one is cited). A null expectation is skipped.

An answer with is_demo=true comes from the demo cache (DEMO_CACHE=true) or from a stub, not
from the live pipeline, so passing it proves nothing about retrieval or the LLM. Such a
turn is printed as DEMO and counts as a failure, unless --allow-demo is given (it is then
still printed as DEMO, and the summary says how many turns were live and how many demo).
To check the live pipeline, run with DEMO_CACHE=false and the real services on.

Never prints the answer text of a passing turn. Exits 1 if any turn fails. Standard library
only, so it runs anywhere Python 3.10+ is installed.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "data" / "eval" / "conversations.json"
TIMEOUT_SECONDS = 180  # a local LLM can take a while on a laptop
MAX_RATE_LIMIT_WAIT = 65  # the chat limit is per minute


def ask(base_url: str, payload: dict) -> tuple[int, dict]:
    """POST one question. Returns (HTTP status, JSON body); status 0 means no response.
    A 429 is retried once after the server's Retry-After."""
    url = f"{base_url.rstrip('/')}/api/v1/chat/ask"
    data = json.dumps(payload).encode()
    for attempt in (1, 2):
        request = urllib.request.Request(
            url, data=data, method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as err:
            body = _json_or_empty(err.read())
            if err.code == 429 and attempt == 1:
                wait = min(int(err.headers.get("Retry-After", "30") or 30), MAX_RATE_LIMIT_WAIT)
                print(f"      rate limited; waiting {wait} s", flush=True)
                time.sleep(wait)
                continue
            return err.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            return 0, {"code": "no_response", "message": str(getattr(err, "reason", err))}
    return 0, {}


def _json_or_empty(raw: bytes) -> dict:
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def check_turn(turn: dict, http_status: int, body: dict) -> list[str]:
    """The reasons this turn failed (empty list = pass)."""
    if http_status != 200:
        detail = f"{body.get('code', '')}: {body.get('message', '')}".strip(": ")
        return [f"HTTP {http_status or 'no response'} {detail}".strip()]

    problems: list[str] = []
    status = body.get("status")
    citations = body.get("citations") or []
    cited_ids = {c.get("document_id") for c in citations}

    # Always checked.
    if not isinstance(body.get("is_demo"), bool):
        problems.append("the response does not say whether it is a demo answer (is_demo)")
    if status == "declined":
        if citations:
            problems.append(f"declined answer carries {len(citations)} citation(s)")
        if not body.get("contact"):
            problems.append("declined answer has no contact")
    if status == "answered" and not citations:
        problems.append("answered without any citation")

    # Checked when the turn asks for it.
    if turn.get("status") is not None and status != turn["status"]:
        problems.append(f"status is {status!r}, expected {turn['status']!r}")
    if turn.get("citations") is True and not citations:
        problems.append("expected citations, got none")
    if turn.get("citations") is False and citations:
        problems.append(f"expected no citations, got {len(citations)}")
    text = (body.get("answer_text") or "").casefold()
    for needle in turn.get("must_contain") or []:
        if needle.casefold() not in text:
            problems.append(f"answer does not contain {needle!r}")
    expected = turn.get("expect_doc_ids") or []
    if expected and not cited_ids & set(expected):
        problems.append(f"none of {expected} is cited (cited: {sorted(cited_ids - {None})})")
    return problems


def load_conversations(path: pathlib.Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        raise SystemExit(f"Cannot read {path}: {err}") from err
    if not isinstance(data, list) or not data:
        raise SystemExit(f"{path} must be a non-empty JSON list of conversations.")
    for conversation in data:
        turns = conversation.get("turns") if isinstance(conversation, dict) else None
        if not turns or not all(isinstance(t, dict) and t.get("text") for t in turns):
            raise SystemExit(f"Conversation {conversation!r:.60} needs turns with a 'text'.")
    return data


class Tally:
    """Counts for the summary."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.live = 0  # answered, is_demo=false
        self.demo = 0  # answered, is_demo=true: the demo cache or a stub
        self.no_answer = 0  # an HTTP error or no response


def run(base_url: str, conversations: list[dict], allow_demo: bool = False) -> Tally:
    tally = Tally()
    for conversation in conversations:
        label = conversation.get("id", "?")
        print(f"\n{label}: {conversation.get('title', '')}")
        conversation_id = None
        for number, turn in enumerate(conversation["turns"], start=1):
            payload = {"text": turn["text"], "language": turn.get("language", "en")}
            if turn.get("state"):
                payload["state"] = turn["state"]
            if conversation_id:
                payload["conversation_id"] = conversation_id
            http_status, body = ask(base_url, payload)
            conversation_id = body.get("conversation_id") or conversation_id

            problems = check_turn(turn, http_status, body)
            where = f"{label} turn {number} [{payload['language']}]"
            is_demo = http_status == 200 and body.get("is_demo") is True
            if http_status != 200:
                tally.no_answer += 1
            elif is_demo:
                tally.demo += 1
            else:
                tally.live += 1

            if problems:
                tally.failed += 1
                kind = " (demo answer)" if is_demo else ""
                print(f"  FAIL  {where}{kind}: " + "; ".join(problems))
                if body.get("answer_text"):
                    print(f"        answer: {body['answer_text'][:160]!r}")
            elif is_demo and not allow_demo:
                tally.failed += 1
                print(
                    f"  DEMO  {where}: demo answer (is_demo=true), not the live pipeline. "
                    "Counted as failed; run with DEMO_CACHE=false and the real services, "
                    "or pass --allow-demo."
                )
            elif is_demo:
                tally.passed += 1
                cited = len(body.get("citations") or [])
                print(
                    f"  DEMO  {where}: {body.get('status')}, {cited} citation(s) "
                    "(demo answer, accepted by --allow-demo)"
                )
            else:
                tally.passed += 1
                cited = len(body.get("citations") or [])
                print(f"  PASS  {where}: {body.get('status')}, {cited} citation(s)")
    return tally


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the chat acceptance conversations.")
    parser.add_argument("base_url", nargs="?", default="http://localhost")
    parser.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    parser.add_argument(
        "--allow-demo",
        action="store_true",
        help="Accept demo answers (is_demo=true: DEMO_CACHE or stubs) instead of failing them.",
    )
    args = parser.parse_args(argv)

    conversations = load_conversations(args.file)
    print(f"Acceptance run against {args.base_url} ({args.file.name})")
    tally = run(args.base_url, conversations, args.allow_demo)
    total = tally.passed + tally.failed
    print(
        f"\nAnswers: {tally.live} live, {tally.demo} demo (is_demo=true), "
        f"{tally.no_answer} without an answer."
    )
    print(f"{total} turn(s): {tally.passed} passed, {tally.failed} failed.")
    if tally.demo and args.allow_demo:
        print(
            f"NOTE: {tally.demo} turn(s) were demo answers, accepted by --allow-demo. "
            "This does not show that the live pipeline works."
        )
    elif tally.demo:
        print(f"{tally.demo} turn(s) were demo answers and count as failed (see --allow-demo).")
    return 1 if tally.failed else 0


if __name__ == "__main__":
    sys.exit(main())
