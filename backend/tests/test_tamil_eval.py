"""scripts/tamil_eval.py against a tiny fake chat server. No network, no model, no LLM."""

import csv
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(settings.BASE_DIR).parent
SCRIPT = ROOT / "scripts" / "tamil_eval.py"
SHIPPED_CSV = ROOT / "data" / "eval" / "tamil_questions.csv"
HEADER = [
    "id", "language", "question_ta", "question_en", "expected_answer_ta",
    "expected_answer_en", "source", "status",
]  # fmt: skip

CITATION = {"document_id": "DOC-1", "title": "Operational Guidelines"}
TAMIL = "இது ஒரு சோதனை பதில்"  # "This is a test answer"


def load_script():
    spec = importlib.util.spec_from_file_location("tamil_eval", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reply(payload: dict) -> dict:
    """The fake chat answer, chosen by the start of the question. A "demo " prefix makes it a
    demo answer."""
    text = payload["text"]
    is_demo = text.startswith("demo ")
    text = text.removeprefix("demo ")
    body = {
        "conversation_id": "conv-1",
        "message_id": "m-1",
        "answer_text": f"{TAMIL} 72 மணி நேரம்.",
        "status": "answered",
        "needs_state": False,
        "citations": [CITATION],
        "followups": [],
        "contact": None,
        "is_demo": is_demo,
    }
    if text.startswith("declined"):
        body |= {"status": "declined", "answer_text": "கிடைக்கவில்லை.", "citations": []}
        body["contact"] = {"label": "Office", "detail": "Details"}
    elif text.startswith("no-number"):
        body["answer_text"] = f"{TAMIL}."
    elif text.startswith("tamil-digits"):
        body["answer_text"] = f"{TAMIL} ௭௨ மணி நேரம்."
    elif text.startswith("wrong-number"):
        body["answer_text"] = f"{TAMIL} 48 மணி நேரம்."
    elif text.startswith("longer-number"):
        body["answer_text"] = f"{TAMIL} 172 மணி நேரம்."
    elif text.startswith("english"):
        body["answer_text"] = "Report the loss within 72 hours of the damage."
    elif text.startswith("echo"):
        body["answer_text"] = f"{TAMIL}. {payload['text']} என்ற கேள்விக்கு பதில் இல்லை."
    elif text.startswith("empty"):
        body["answer_text"] = ""
    elif text.startswith("no-citation"):
        body["citations"] = []
    elif text.startswith("compulsory"):
        body["answer_text"] = f"{TAMIL}: காப்பீடு கட்டாயம் ஆகும்."
    elif text.startswith("voluntary"):
        body["answer_text"] = f"{TAMIL}: இது தன்னார்வ பதிவு."
    elif text.startswith("long"):
        body["answer_text"] = TAMIL + " " + "அ" * 500
    return body


@pytest.fixture
def chat_server():
    state = {"requests": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(reply(payload)).encode())

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    yield state
    httpd.shutdown()


def write_csv(tmp_path: Path, *rows: tuple, bom: bool = True) -> Path:
    """Rows are (id, question, status, expected_answer_en)."""
    path = tmp_path / "questions.csv"
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for qid, question, status, expected in rows:
            writer.writerow([qid, "ta", question, "q", "", expected, "source", status])
    return path


def run_eval(url: str, path: Path, capsys, *extra: str) -> tuple[int, str]:
    code = load_script().main([url, "--file", str(path), *extra])
    return code, capsys.readouterr().out


CHECKED_72 = "Report the loss within 72 hours of the damage."


# --- parsing and numbers ----------------------------------------------------------------


def test_the_shipped_csv_parses_with_commas_inside_quoted_cells():
    rows = load_script().load_rows(SHIPPED_CSV)
    assert [r["id"] for r in rows] == [f"T{n:02d}" for n in range(1, 21)]
    by_id = {r["id"]: r for r in rows}
    assert by_id["T02"]["expected_answer_en"].startswith("Directly to the insurance company, the")
    assert by_id["T08"]["status"] == "CONFLICT, resolve first"
    assert all(r["language"] == "ta" and r["question_ta"] for r in rows)


def test_a_bom_is_ignored_and_quoted_commas_survive(tmp_path):
    path = write_csv(tmp_path, ("X1", "கேள்வி, ஒன்று?", "CHECK", "One, two and 3."))
    rows = load_script().load_rows(path)
    assert rows[0]["id"] == "X1"  # not "﻿id"
    assert rows[0]["question_ta"] == "கேள்வி, ஒன்று?"


def test_key_numbers_come_from_the_expected_english_answer():
    script = load_script()
    rows = {r["id"]: r for r in script.load_rows(SHIPPED_CSV)}
    assert script.key_numbers(rows["T01"]["expected_answer_en"]) == ["72"]
    assert script.key_numbers(rows["T13"]["expected_answer_en"]) == ["72"]
    assert script.key_numbers(rows["T14"]["expected_answer_en"]) == ["48"]
    assert script.key_numbers(rows["T02"]["expected_answer_en"]) == []
    assert script.key_numbers("1.5% or 2% or 1.5%") == ["1.5", "2"]


def test_status_kinds():
    script = load_script()
    assert script.status_kind("CHECKED") == "CHECKED"
    assert script.status_kind("CHECKED, list incomplete") == "CHECKED"
    assert script.status_kind("CHECK") == "CHECK"
    assert script.status_kind("CONFLICT, resolve first") == "CONFLICT"
    assert script.status_kind("NEEDS SOURCE") == "NEEDS SOURCE"
    assert script.status_kind("verified by me") == "UNKNOWN"


# --- the requests ------------------------------------------------------------------------


def test_each_question_is_asked_in_tamil_for_tn(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "ta question one", "CHECKED", CHECKED_72))
    run_eval(chat_server["url"], path, capsys)
    assert chat_server["requests"] == [{"text": "ta question one", "language": "ta", "state": "TN"}]


# --- invariants: every row ---------------------------------------------------------------


@pytest.mark.parametrize("status", ["CHECKED", "CHECK", "CONFLICT", "NEEDS SOURCE"])
@pytest.mark.parametrize(
    ("question", "reason"),
    [
        ("empty answer", "answer is empty"),
        ("english answer", "answered without Tamil script"),
        ("echo answer here", "answer repeats the question"),
        ("no-citation answer", "answered without any citation"),
        ("demo answer", "demo answer"),
    ],
)
def test_invariants_fail_any_row(chat_server, tmp_path, capsys, status, question, reason):
    path = write_csv(tmp_path, ("A", question, status, CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 1
    assert reason in out and "FAIL" in out


def test_allow_demo_accepts_a_demo_answer(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "demo question", "CHECKED", CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys, "--allow-demo")
    assert code == 0
    assert "demo=yes" in out and "1 demo" in out


def test_an_unreachable_server_fails_every_row(tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "question", "CHECK", ""))
    code, out = run_eval("http://127.0.0.1:9", path, capsys)
    assert code == 1 and "no response" in out


# --- content checks: CHECKED rows only ---------------------------------------------------


def test_a_checked_row_passes_when_its_key_number_is_in_the_answer(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "question", "CHECKED", CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 0
    assert "PASS" in out and "numbers=72:ok" in out


def test_tamil_digits_count_as_the_number(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "tamil-digits question", "CHECKED", CHECKED_72))
    assert run_eval(chat_server["url"], path, capsys)[0] == 0


@pytest.mark.parametrize("question", ["wrong-number question", "longer-number question"])
def test_a_checked_row_fails_on_a_missing_number(chat_server, tmp_path, capsys, question):
    path = write_csv(tmp_path, ("A", question, "CHECKED", CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 1
    assert "key number(s) 72 not in the answer" in out and "72:MISSING" in out


def test_a_checked_row_fails_when_declined(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "declined question", "CHECKED", CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 1 and "declined a question that has a verified answer" in out


def test_a_checked_row_without_numbers_has_no_content_check(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "no-number question", "CHECKED, list incomplete", "Ask X."))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 0 and "numbers=-" in out


def test_a_passing_checked_row_prints_no_answer_text(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "question", "CHECKED", CHECKED_72))
    _, out = run_eval(chat_server["url"], path, capsys)
    assert TAMIL not in out and "UNVERIFIED, read by a person" not in out


# --- unverified rows never pass or fail on content ---------------------------------------


@pytest.mark.parametrize("status", ["CHECK", "CONFLICT", "NEEDS SOURCE", "something else"])
@pytest.mark.parametrize("question", ["wrong-number question", "declined question"])
def test_unverified_rows_never_fail_on_content(chat_server, tmp_path, capsys, status, question):
    path = write_csv(tmp_path, ("A", question, status, CHECKED_72))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 0
    assert "REVIEW" in out and "PASS" not in out
    assert "UNVERIFIED, read by a person" in out


def test_unverified_answers_are_cut_to_200_characters(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "long question", "CHECK", ""))
    _, out = run_eval(chat_server["url"], path, capsys)
    full = TAMIL + " " + "அ" * 500
    assert full[:200] in out
    assert full[:201] not in out and full not in out


# --- the T08 warning ---------------------------------------------------------------------


@pytest.mark.parametrize("question", ["compulsory question", "voluntary question"])
def test_a_conflict_answer_that_takes_a_side_is_flagged(chat_server, tmp_path, capsys, question):
    path = write_csv(tmp_path, ("T08", question, "CONFLICT, resolve first", ""))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 0  # a warning, not a failure
    assert "WARNING" in out and "a person must review it" in out


def test_a_neutral_conflict_answer_has_no_warning(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("T08", "no-number question", "CONFLICT, resolve first", ""))
    code, out = run_eval(chat_server["url"], path, capsys)
    assert code == 0 and "WARNING" not in out


def test_other_rows_get_no_conflict_warning(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("T09", "compulsory question", "CHECK", ""))
    assert "WARNING" not in run_eval(chat_server["url"], path, capsys)[1]


# --- output files ------------------------------------------------------------------------


def test_no_file_is_written_by_default(chat_server, tmp_path, capsys):
    path = write_csv(tmp_path, ("A", "question", "CHECK", ""))
    before = {p.name for p in tmp_path.iterdir()}
    run_eval(chat_server["url"], path, capsys)
    assert {p.name for p in tmp_path.iterdir()} == before


def test_csv_out_writes_the_table_without_answer_text(chat_server, tmp_path, capsys):
    path = write_csv(
        tmp_path,
        ("A", "question", "CHECKED", CHECKED_72),
        ("B", "long question", "CHECK", ""),
    )
    out_path = tmp_path / "table.csv"
    run_eval(chat_server["url"], path, capsys, "--csv-out", str(out_path))
    text = out_path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    assert [(r["id"], r["result"]) for r in rows] == [("A", "PASS"), ("B", "REVIEW")]
    assert rows[0]["first_citation"] == "Operational Guidelines" and rows[0]["cites"] == "1"
    assert TAMIL not in text
