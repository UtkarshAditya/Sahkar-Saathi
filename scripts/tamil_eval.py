#!/usr/bin/env python3
"""Run the Tamil evaluation questions through the chat API and report on each answer.

    python scripts/tamil_eval.py [BASE_URL] [--file data/eval/tamil_questions.csv]
                                 [--state TN] [--allow-demo] [--csv-out PATH]

BASE_URL defaults to http://localhost (docker compose). Each question_ta is asked on its own,
as a new conversation, through POST /api/v1/chat/ask with the row's language (ta) and the
state (TN by default). The CSV columns and statuses are described in data/eval/README.md.

Invariants, checked on EVERY row (a violation is a FAIL):
- the request succeeded (HTTP 200);
- the answer is not empty;
- an answered row has Tamil script (at least half of its letters; PMFBY and other Latin
  acronyms are fine);
- the answer does not repeat the question text;
- an answered row has at least one citation;
- the answer is not a demo answer (is_demo=true: the demo cache or a stub), unless
  --allow-demo is given. A demo answer proves nothing about retrieval or the model.

Content check, on CHECKED rows ONLY: the declined answer fails, and so does an answer that
lacks any of the key numbers of expected_answer_en. The key numbers are the digit groups in
that English sentence (T01: 72), compared with the digits of the answer (Tamil digits count).
A CHECKED row with no number in its expected answer has no content check.

Rows with any other status (CHECK, CONFLICT, NEEDS SOURCE, anything unknown) are
UNVERIFIED: their answers are shown, cut to 200 characters, labelled "UNVERIFIED, read by a
person", and never pass or fail on content. They can still FAIL an invariant. For a CONFLICT
row a warning line is printed if the answer uses "compulsory" or "voluntary" language, so a
person reviews it. Only a person can change a row's status in the CSV.

Nothing is written unless --csv-out is given: it saves the table (no answer text). Full
answers are never printed or stored; the 200-character preview is the most that is shown.
Exits 1 if any row fails. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import pathlib
import re
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "data" / "eval" / "tamil_questions.csv"
REQUIRED_COLUMNS = ("id", "language", "question_ta", "expected_answer_en", "status")
PREVIEW_CHARS = 200
TITLE_CHARS = 36

# Wording that settles the T08 conflict one way or the other; a person must read such an answer.
CONFLICT_TERMS = (
    "compulsory", "mandatory", "voluntary", "optional",
    "கட்டாய", "தன்னார்வ", "விருப்ப",
)  # fmt: skip

TABLE_COLUMNS = (
    "id", "status", "answer", "tamil", "echo", "cites", "first_citation", "seconds", "demo",
    "numbers", "result", "notes",
)  # fmt: skip


def _load_acceptance():
    """scripts/acceptance.py, loaded by path: its ask() and script helpers are reused so the
    base URL, rate-limit retry and Tamil-script test behave exactly as in the acceptance run."""
    path = pathlib.Path(__file__).resolve().parent / "acceptance.py"
    spec = importlib.util.spec_from_file_location("acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acceptance = _load_acceptance()


def load_rows(path: pathlib.Path) -> list[dict]:
    """The CSV rows (UTF-8, a BOM is ignored; commas inside quoted cells are kept)."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise SystemExit(f"{path} lacks the column(s): {', '.join(missing)}")
            rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    except OSError as err:
        raise SystemExit(f"Cannot read {path}: {err}") from err
    for row in rows:
        if not (row["id"] or "").strip() or not (row["question_ta"] or "").strip():
            raise SystemExit(f"{path}: every row needs an id and a question_ta (got {row!r:.80})")
    if not rows:
        raise SystemExit(f"{path} has no questions.")
    return rows


def status_kind(status: str) -> str:
    """CHECKED, CHECK, CONFLICT or NEEDS SOURCE from a status cell such as "CHECKED, list
    incomplete"; anything else is "UNKNOWN". Only CHECKED is trusted."""
    head = (status or "").split(",")[0].split(":")[0].strip().upper()
    return head if head in {"CHECKED", "CHECK", "CONFLICT", "NEEDS SOURCE"} else "UNKNOWN"


def _ascii_digits(text: str) -> str:
    """Tamil (and other) decimal digits as ASCII, so "௭௨" counts as 72."""
    return "".join(
        str(unicodedata.decimal(c)) if unicodedata.category(c) == "Nd" else c for c in text
    )


def key_numbers(expected_en: str) -> list[str]:
    """The numbers in the expected English answer, in order, without repeats."""
    return list(dict.fromkeys(re.findall(r"\d+(?:\.\d+)?", _ascii_digits(expected_en or ""))))


def number_in(number: str, text: str) -> bool:
    """True if the number appears as a whole number in the text (72 is not in 172 or 7.2)."""
    pattern = rf"(?<!\d)(?<!\d\.){re.escape(number)}(?!\.?\d)"
    return re.search(pattern, _ascii_digits(text)) is not None


def preview(text: str) -> str:
    flat = " ".join((text or "").split())
    return flat[:PREVIEW_CHARS] + ("…" if len(flat) > PREVIEW_CHARS else "")


def evaluate(row: dict, http_status: int, body: dict, allow_demo: bool = False) -> dict:
    """Judge one answer. Returns the table cells plus ``failures`` (reasons) and ``warning``."""
    kind = status_kind(row["status"])
    text = body.get("answer_text") or ""
    status = body.get("status") if http_status == 200 else None
    citations = body.get("citations") or []
    failures: list[str] = []

    share = acceptance.script_share(text, "Tamil")
    has_tamil = share is not None and share >= acceptance.MIN_SCRIPT_SHARE
    echoed_question = acceptance._squash(row["question_ta"])
    echoed = len(
        echoed_question
    ) >= acceptance.MIN_ECHO_CHARS and echoed_question in acceptance._squash(text)
    is_demo = body.get("is_demo")

    if http_status != 200:
        detail = f"{body.get('code', '')}: {body.get('message', '')}".strip(": ")
        failures.append(f"HTTP {http_status or 'no response'} {detail}".strip())
    else:
        if not text.strip():
            failures.append("answer is empty")
        if status == "answered" and text.strip() and not has_tamil:
            failures.append("answered without Tamil script")
        if echoed:
            failures.append("answer repeats the question")
        if status == "answered" and not citations:
            failures.append("answered without any citation")
        if not isinstance(is_demo, bool):
            failures.append("the response does not say whether it is a demo answer (is_demo)")
        elif is_demo and not allow_demo:
            failures.append("demo answer (is_demo=true), not the live pipeline")

    numbers = "-"
    if kind == "CHECKED" and http_status == 200:
        wanted = key_numbers(row.get("expected_answer_en", ""))
        if status != "answered":
            failures.append("declined a question that has a verified answer")
        found = [n for n in wanted if number_in(n, text)]
        lacking = [n for n in wanted if n not in found]
        if wanted:
            numbers = " ".join(f"{n}:{'ok' if n in found else 'MISSING'}" for n in wanted)
        if status == "answered" and lacking:
            failures.append(f"key number(s) {', '.join(lacking)} not in the answer")

    warning = ""
    if kind == "CONFLICT" and http_status == 200:
        lowered = text.casefold()
        used = [t for t in CONFLICT_TERMS if t in lowered]
        if used:
            warning = (
                f"answer uses {', '.join(repr(t) for t in used)}: the sources disagree on this "
                "question, a person must review it"
            )

    verified = kind == "CHECKED"
    result = "FAIL" if failures else ("PASS" if verified else "REVIEW")
    return {
        "id": row["id"],
        "status": row["status"].strip(),
        "answer": status or "no answer",
        "tamil": "yes" if has_tamil else "no",
        "echo": "yes" if echoed else "no",
        "cites": len(citations),
        "first_citation": (citations[0].get("title") or "")[:TITLE_CHARS] if citations else "-",
        "demo": "yes" if is_demo is True else "no",
        "numbers": numbers,
        "result": result,
        "notes": "; ".join(failures),
        "failures": failures,
        "warning": warning,
        "kind": kind,
        "preview": "" if verified else preview(text),
    }


def ask_row(base_url: str, row: dict, state: str | None) -> tuple[int, dict, float]:
    payload = {"text": row["question_ta"].strip(), "language": (row["language"] or "ta").strip()}
    if state:
        payload["state"] = state
    started = time.perf_counter()
    http_status, body = acceptance.ask(base_url, payload)
    return http_status, body, time.perf_counter() - started


def print_row(cells: dict) -> None:
    print(
        f"{cells['result']:<6} {cells['id']:<4} {cells['status'][:24]:<24} {cells['answer']:<9} "
        f"tamil={cells['tamil']:<3} echo={cells['echo']:<3} cites={cells['cites']} "
        f"{cells['first_citation']:<{TITLE_CHARS}} {cells['seconds']:>6}s "
        f"demo={cells['demo']:<3} numbers={cells['numbers']}",
        flush=True,
    )
    if cells["kind"] != "CHECKED":
        label = "UNVERIFIED, read by a person"
        print(f"       {label}: {cells['preview'] or '(no answer text)'}")
    if cells["warning"]:
        print(f"       WARNING: {cells['warning']}")
    for reason in cells["failures"]:
        print(f"       FAIL: {reason}")


def write_csv(path: pathlib.Path, results: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TABLE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def run(base_url: str, rows: list[dict], state: str | None, allow_demo: bool = False) -> list[dict]:
    results = []
    for row in rows:
        http_status, body, seconds = ask_row(base_url, row, state)
        cells = evaluate(row, http_status, body, allow_demo)
        cells["seconds"] = f"{seconds:.1f}"
        results.append(cells)
        print_row(cells)
    return results


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        # Tamil text must not raise UnicodeEncodeError on a legacy Windows console.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the Tamil evaluation questions.")
    parser.add_argument("base_url", nargs="?", default="http://localhost")
    parser.add_argument("--file", type=pathlib.Path, default=DEFAULT_FILE)
    parser.add_argument("--state", default="TN", help="State code sent with each question.")
    parser.add_argument(
        "--allow-demo",
        action="store_true",
        help="Accept demo answers (is_demo=true: DEMO_CACHE or stubs) instead of failing them.",
    )
    parser.add_argument("--csv-out", type=pathlib.Path, help="Also write the table here.")
    args = parser.parse_args(argv)

    rows = load_rows(args.file)
    print(f"Tamil evaluation against {args.base_url} ({args.file.name}, {len(rows)} questions)\n")
    results = run(args.base_url, rows, args.state or None, args.allow_demo)

    counts = {
        name: sum(r["result"] == name for r in results) for name in ("PASS", "REVIEW", "FAIL")
    }
    demo = sum(r["demo"] == "yes" for r in results)
    print(
        f"\n{len(results)} question(s): {counts['PASS']} passed (CHECKED), "
        f"{counts['REVIEW']} UNVERIFIED for a person to read, {counts['FAIL']} failed."
    )
    print(f"Answers: {len(results) - demo} live or missing, {demo} demo (is_demo=true).")
    if counts["REVIEW"]:
        print("REVIEW rows were not judged on content. Only a person can mark a row CHECKED.")
    if args.csv_out:
        write_csv(args.csv_out, results)
        print(f"Table written to {args.csv_out}")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
