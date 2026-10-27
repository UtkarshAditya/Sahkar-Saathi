"""The two objective-test tools: `manage.py eval_retrieval` (with a fake retriever) and
`scripts/acceptance.py` (against a tiny fake chat server). No network, no model, no LLM."""

import importlib.util
import io
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.management.commands import eval_retrieval as eval_module
from services.types import Passage, ServiceNotReady

ROOT = Path(settings.BASE_DIR).parent
EVAL_DIR = ROOT / "data" / "eval"


# --- eval_retrieval -------------------------------------------------------------------


def passage(doc_id: str, score: float) -> Passage:
    return Passage(
        chunk_id=f"chunk-{doc_id}",
        text="text",
        document_id=doc_id,
        document_title=doc_id,
        publisher="Test",
        source_url=None,
        published_date=None,
        page=1,
        score=score,
        state=None,
    )


class FakeRetriever:
    """Scripted: {question id: (score, document id)}; remembers how it was called."""

    def __init__(self, script: dict[str, tuple[float, str]], questions: list[dict]):
        self.by_text = {q["question"]: q["id"] for q in questions}
        self.script = script
        self.calls: list[dict] = []

    async def search(self, query, *, state, language, top_k=4, document_id=None):
        self.calls.append({"query": query, "state": state, "language": language, "top_k": top_k})
        score, doc_id = self.script[self.by_text[query]]
        return [passage(doc_id, score), passage("OTHER", score / 2)][:top_k]


def question(qid: str, in_scope: bool, expect: list[str] | None = None, state=None) -> dict:
    return {
        "id": qid,
        "question": f"Question {qid}?",
        "state": state,
        "in_scope": in_scope,
        "expect_doc_ids": expect or [],
    }


def write_questions(tmp_path: Path, questions: list[dict]) -> Path:
    path = tmp_path / "questions.json"
    path.write_text(json.dumps(questions), encoding="utf-8")
    return path


def run_eval(monkeypatch, tmp_path, questions, script, *args) -> tuple[str, FakeRetriever]:
    fake = FakeRetriever(script, questions)
    monkeypatch.setattr(eval_module, "get_retriever", lambda: fake)
    out = io.StringIO()
    call_command(
        "eval_retrieval", "--questions", str(write_questions(tmp_path, questions)), *args,
        stdout=out,
    )  # fmt: skip
    return out.getvalue(), fake


def separated_set() -> tuple[list[dict], dict]:
    questions = [question(f"in{i}", True, ["DOC-A"], state="TN") for i in range(6)]
    questions += [question(f"out{i}", False) for i in range(5)]
    in_scores = [0.80, 0.75, 0.70, 0.65, 0.60, 0.55]
    out_scores = [0.30, 0.25, 0.35, 0.20, 0.28]
    script = {f"in{i}": (s, "DOC-A") for i, s in enumerate(in_scores)}
    script["in5"] = (0.55, "DOC-WRONG")  # one in-scope question misses its document
    script |= {f"out{i}": (s, "DOC-B") for i, s in enumerate(out_scores)}
    return questions, script


def test_prints_each_question_the_hit_rate_and_a_suggested_threshold(monkeypatch, tmp_path):
    questions, script = separated_set()
    out, fake = run_eval(monkeypatch, tmp_path, questions, script)

    assert "11 questions" in out
    lines = {line.split()[0]: line for line in out.splitlines() if line[:2] in {"in", "ou"}}
    assert lines["in0"].split()[1:4] == ["in", "0.800", "DOC-A"] and lines["in0"].endswith("hit")
    assert lines["in5"].endswith("MISS")
    assert lines["out0"].split()[1:4] == ["out", "0.300", "DOC-B"] and lines["out0"].endswith("-")
    assert "Hit rate (expected document in the top 4): 5/6" in out
    assert "In-scope top scores (6): mean 0.675, min 0.550, max 0.800" in out
    assert "Out-of-scope top scores (5): mean 0.276, min 0.200, max 0.350" in out
    # 10th percentile of in-scope = 0.575, 90th percentile of out-of-scope = 0.330.
    assert "SUGGESTED SCORE_THRESHOLD=0.45" in out
    assert "overlap" not in out and "WARNING" not in out
    assert "6/6 in-scope pass" in out and "5/5 out blocked" in out

    # The retriever got the question, its state, English and the default top-k.
    assert {c["language"] for c in fake.calls} == {"en"}
    assert {c["top_k"] for c in fake.calls} == {settings.TOP_K}
    assert fake.calls[0]["state"] == "TN" and fake.calls[-1]["state"] is None


def test_top_k_option_is_passed_on_and_used_for_the_hit_check(monkeypatch, tmp_path):
    questions = [question("q", True, ["DOC-OTHER"])]
    script = {"q": (0.9, "DOC-A")}
    out, fake = run_eval(monkeypatch, tmp_path, questions, script, "--top-k", "1")
    assert fake.calls[0]["top_k"] == 1
    assert "Hit rate (expected document in the top 1): 0/1" in out


def test_warns_when_the_score_ranges_overlap(monkeypatch, tmp_path):
    questions = [question(f"in{i}", True, ["DOC-A"]) for i in range(5)]
    questions += [question(f"out{i}", False) for i in range(5)]
    script = {f"in{i}": (s, "DOC-A") for i, s in enumerate([0.9, 0.8, 0.7, 0.6, 0.5])}
    script |= {f"out{i}": (s, "DOC-B") for i, s in enumerate([0.8, 0.7, 0.6, 0.5, 0.4])}
    out, _ = run_eval(monkeypatch, tmp_path, questions, script)
    assert "the score ranges overlap" in out
    assert "SUGGESTED SCORE_THRESHOLD=" in out


def test_warns_when_a_group_has_fewer_than_five_questions(monkeypatch, tmp_path):
    questions = [question("in0", True), question("in1", True), question("out0", False)]
    script = {"in0": (0.8, "A"), "in1": (0.7, "A"), "out0": (0.2, "B")}
    out, _ = run_eval(monkeypatch, tmp_path, questions, script)
    assert "only 2 in-scope questions" in out
    assert "only 1 out-of-scope questions" in out


def test_questions_without_expected_documents_only_count_for_the_threshold(monkeypatch, tmp_path):
    questions = [question(f"in{i}", True) for i in range(5)] + [question("out", False)]
    script = {f"in{i}": (0.7, "A") for i in range(5)} | {"out": (0.2, "B")}
    out, _ = run_eval(monkeypatch, tmp_path, questions, script)
    assert "Hit rate: n/a" in out
    assert "In-scope top scores (5)" in out


def test_a_group_with_no_questions_gives_no_suggestion(monkeypatch, tmp_path):
    out, _ = run_eval(monkeypatch, tmp_path, [question("in", True)], {"in": (0.7, "A")})
    assert "No SUGGESTED SCORE_THRESHOLD" in out


def test_a_retriever_failure_is_a_clear_error(monkeypatch, tmp_path):
    class Broken:
        async def search(self, *args, **kwargs):
            raise ServiceNotReady("The retriever is unavailable.")

    monkeypatch.setattr(eval_module, "get_retriever", lambda: Broken())
    path = write_questions(tmp_path, [question("q", True)])
    with pytest.raises(CommandError, match="failed on 'q'.*retriever is unavailable"):
        call_command("eval_retrieval", "--questions", str(path), stdout=io.StringIO())


def test_works_through_get_retriever_with_the_stub_and_says_so(settings, tmp_path):
    settings.USE_STUB_RETRIEVER = True
    path = write_questions(tmp_path, [question("pmfby", True), question("noise", False)])
    out = io.StringIO()
    call_command("eval_retrieval", "--questions", str(path), stdout=out)
    assert "USE_STUB_RETRIEVER is on" in out.getvalue()
    assert "pmfby" in out.getvalue()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "not valid JSON"),
        ("[]", "non-empty JSON list"),
        ('[{"id": "a", "question": "q"}]', "needs 'in_scope'"),
        ('[{"id": "a", "question": "", "in_scope": true}]', "needs 'question'"),
        (
            '[{"id": "a", "question": "q", "in_scope": true, "expect_doc_ids": "DOC"}]',
            "list of document ids",
        ),
        (
            '[{"id": "a", "question": "q", "in_scope": true},'
            ' {"id": "a", "question": "r", "in_scope": false}]',
            "appears twice",
        ),
    ],
)
def test_a_bad_question_file_is_a_clear_error(tmp_path, content, message):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CommandError, match=message):
        call_command("eval_retrieval", "--questions", str(path), stdout=io.StringIO())


def test_a_missing_question_file_is_a_clear_error(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command("eval_retrieval", "--questions", str(tmp_path / "no.json"))


def test_percentile_interpolates():
    assert eval_module.percentile([1.0], 10) == 1.0
    assert eval_module.percentile([0.0, 1.0], 50) == 0.5
    assert eval_module.percentile([0.55, 0.6, 0.65, 0.7, 0.75, 0.8], 10) == pytest.approx(0.575)


def test_the_committed_question_file_is_valid():
    questions = eval_module.load_questions(EVAL_DIR / "retrieval_questions.json")
    assert any(q["in_scope"] for q in questions) and any(not q["in_scope"] for q in questions)
    assert all(q["expect_doc_ids"] == [] for q in questions if q.get("TODO_owner")), (
        "expect_doc_ids are the owner's to fill in; do not guess them"
    )


# --- scripts/acceptance.py ------------------------------------------------------------


def load_acceptance():
    path = ROOT / "scripts" / "acceptance.py"
    spec = importlib.util.spec_from_file_location("acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CITATION = {"document_id": "DOC-1", "title": "A document"}
CONTACT = {"label": "District office", "detail": "Details"}


def reply(payload: dict) -> dict:
    """What the fake chat endpoint answers, chosen by the start of the question. A "demo "
    prefix makes it a demo-cache answer (is_demo=true); "no-flag " leaves is_demo out."""
    text = payload["text"]
    is_demo = text.startswith("demo ")
    omit_flag = text.startswith("no-flag ")
    text = text.removeprefix("demo ").removeprefix("no-flag ")
    body = {
        "conversation_id": payload.get("conversation_id") or "conv-1",
        "message_id": "m-1",
        "answer_text": "Report within 72 hours.",
        "status": "answered",
        "needs_state": False,
        "citations": [CITATION],
        "followups": [],
        "contact": None,
        "is_demo": is_demo,
    }
    if text.startswith("declined-ok"):
        body |= {"status": "declined", "answer_text": "Not found.", "citations": []}
        body["contact"] = CONTACT
    elif text.startswith("declined-no-contact"):
        body |= {"status": "declined", "citations": []}
    elif text.startswith("declined-cited"):
        body |= {"status": "declined", "contact": CONTACT}
    elif text.startswith("answered-bare"):
        body |= {"citations": []}
    if omit_flag:
        del body["is_demo"]
    return body


@pytest.fixture
def chat_server():
    state = {"requests": [], "rate_limit_first": False}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(payload)
            if state["rate_limit_first"]:
                state["rate_limit_first"] = False
                body, status, extra = {"code": "rate_limited", "message": "Slow down."}, 429, True
            else:
                body, status, extra = reply(payload), 200, False
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if extra:
                self.send_header("Retry-After", "0")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    yield state
    httpd.shutdown()


def write_conversations(tmp_path: Path, conversations: list[dict]) -> str:
    path = tmp_path / "conversations.json"
    path.write_text(json.dumps(conversations), encoding="utf-8")
    return str(path)


def conversation(*turns: dict, cid: str = "c1") -> dict:
    return {"id": cid, "title": "Test conversation", "turns": list(turns)}


def run_acceptance(url: str, file: str, capsys, *extra: str) -> tuple[int, str]:
    code = load_acceptance().main([url, "--file", file, *extra])
    return code, capsys.readouterr().out


def test_demo_answers_fail_by_default_and_are_printed_as_demo(chat_server, tmp_path, capsys):
    turns = [{"text": "cited live"}, {"text": "demo cited cached"}]
    file = write_conversations(tmp_path, [conversation(*turns)])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 1, "a demo answer is not evidence that the live pipeline works"
    assert out.count("  PASS  ") == 1 and out.count("  DEMO  ") == 1
    assert "demo answer (is_demo=true), not the live pipeline" in out
    assert "Answers: 1 live, 1 demo (is_demo=true), 0 without an answer." in out
    assert "2 turn(s): 1 passed, 1 failed." in out
    assert "1 turn(s) were demo answers and count as failed" in out


def test_allow_demo_accepts_them_but_still_prints_demo_and_says_so(chat_server, tmp_path, capsys):
    turns = [{"text": "cited live"}, {"text": "demo cited cached"}]
    file = write_conversations(tmp_path, [conversation(*turns)])
    code, out = run_acceptance(chat_server["url"], file, capsys, "--allow-demo")
    assert code == 0, out
    assert out.count("  PASS  ") == 1 and out.count("  DEMO  ") == 1
    assert "(demo answer, accepted by --allow-demo)" in out
    assert "Answers: 1 live, 1 demo (is_demo=true), 0 without an answer." in out
    assert "2 turn(s): 2 passed, 0 failed." in out
    assert "NOTE: 1 turn(s) were demo answers" in out and "does not show" in out


def test_a_run_of_only_demo_answers_is_never_reported_as_live(chat_server, tmp_path, capsys):
    turns = [{"text": "demo cited a"}, {"text": "demo declined-ok"}]
    file = write_conversations(tmp_path, [conversation(*turns)])
    _, out = run_acceptance(chat_server["url"], file, capsys, "--allow-demo")
    assert "PASS" not in out and out.count("  DEMO  ") == 2
    assert "Answers: 0 live, 2 demo" in out


def test_a_demo_answer_that_also_breaks_an_expectation_is_a_fail(chat_server, tmp_path, capsys):
    file = write_conversations(
        tmp_path, [conversation({"text": "demo cited a", "must_contain": ["nowhere"]})]
    )
    code, out = run_acceptance(chat_server["url"], file, capsys, "--allow-demo")
    assert code == 1 and "FAIL  c1 turn 1 [en] (demo answer):" in out
    assert "answer does not contain 'nowhere'" in out


def test_a_response_without_is_demo_fails(chat_server, tmp_path, capsys):
    file = write_conversations(tmp_path, [conversation({"text": "no-flag cited a"})])
    code, out = run_acceptance(chat_server["url"], file, capsys, "--allow-demo")
    assert code == 1 and "does not say whether it is a demo answer (is_demo)" in out


def test_passing_turns_pass_and_never_print_the_answer(chat_server, tmp_path, capsys):
    turns = [
        {"text": "cited one", "status": "answered", "citations": True, "must_contain": ["72"]},
        {"text": "declined-ok", "status": "declined", "citations": False},
        {"text": "cited two", "expect_doc_ids": ["DOC-1", "DOC-9"], "must_contain": ["HOURS"]},
    ]
    file = write_conversations(tmp_path, [conversation(*turns)])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 0, out
    assert out.count("PASS") == 3 and "FAIL" not in out and "DEMO" not in out
    assert "Answers: 3 live, 0 demo (is_demo=true), 0 without an answer." in out
    assert "3 turn(s): 3 passed, 0 failed." in out
    assert "Report within 72 hours" not in out and "Not found." not in out


def test_each_unmet_expectation_fails_with_its_reason(chat_server, tmp_path, capsys):
    turns = [
        {"text": "cited a", "status": "declined"},
        {"text": "cited b", "citations": False},
        {"text": "cited c", "must_contain": ["nowhere"]},
        {"text": "cited d", "expect_doc_ids": ["DOC-9"]},
        {"text": "declined-ok", "citations": True},
    ]
    file = write_conversations(tmp_path, [conversation(*turns)])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 1
    assert "status is 'answered', expected 'declined'" in out
    assert "expected no citations, got 1" in out
    assert "answer does not contain 'nowhere'" in out
    assert "none of ['DOC-9'] is cited" in out
    assert "expected citations, got none" in out
    assert "0 passed, 5 failed" in out
    assert "answer: 'Report within 72 hours.'" in out, "a failing turn shows what was said"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("declined-no-contact", "declined answer has no contact"),
        ("declined-cited", "declined answer carries 1 citation(s)"),
        ("answered-bare", "answered without any citation"),
    ],
)
def test_the_invariants_are_always_checked(chat_server, tmp_path, capsys, text, reason):
    file = write_conversations(tmp_path, [conversation({"text": text, "status": None})])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 1 and reason in out


def test_follow_up_turns_reuse_the_conversation_and_send_language_and_state(
    chat_server, tmp_path, capsys
):
    turns = [
        {"text": "cited first", "language": "hi", "state": "TN"},
        {"text": "cited second", "language": "ta"},
    ]
    file = write_conversations(tmp_path, [conversation(*turns)])
    code, _ = run_acceptance(chat_server["url"], file, capsys)
    first, second = chat_server["requests"]
    assert code == 0
    assert first["language"] == "hi" and first["state"] == "TN" and "conversation_id" not in first
    assert second["language"] == "ta" and second["conversation_id"] == "conv-1"
    assert "state" not in second


def test_null_expectations_are_skipped(chat_server, tmp_path, capsys):
    turn = {"text": "cited x", "status": None, "citations": None, "TODO_owner": "Varsha"}
    file = write_conversations(tmp_path, [conversation(turn)])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 0 and "PASS" in out


def test_a_rate_limited_turn_is_retried_once(chat_server, tmp_path, capsys):
    chat_server["rate_limit_first"] = True
    file = write_conversations(tmp_path, [conversation({"text": "cited x"})])
    code, out = run_acceptance(chat_server["url"], file, capsys)
    assert code == 0 and "rate limited" in out
    assert len(chat_server["requests"]) == 2


def test_an_unreachable_server_fails_every_turn(tmp_path, capsys):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]  # nothing listens here once the socket is closed
    file = write_conversations(tmp_path, [conversation({"text": "cited x"})])
    code, out = run_acceptance(f"http://127.0.0.1:{port}", file, capsys)
    assert code == 1 and "FAIL" in out and "no response" in out
    assert "Answers: 0 live, 0 demo (is_demo=true), 1 without an answer." in out


@pytest.mark.parametrize("content", ["not json", "[]", '[{"id": "c", "turns": []}]'])
def test_a_bad_conversation_file_stops_the_run(tmp_path, content):
    path = tmp_path / "c.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit):
        load_acceptance().main(["http://127.0.0.1:1", "--file", str(path)])


def test_the_committed_conversations_have_the_five_scenarios():
    conversations = load_acceptance().load_conversations(EVAL_DIR / "conversations.json")
    by_id = {c["id"]: c for c in conversations}
    assert len(conversations) == 5

    english = by_id["pmfby-loss-en"]["turns"][0]
    assert english["must_contain"] == ["72"] and english["citations"] is True

    languages = [t["language"] for t in by_id["pmfby-loss-hi-ta"]["turns"]]
    assert languages == ["hi", "ta"]

    assert by_id["coop-member-tn"]["turns"][0]["state"] == "TN"
    assert by_id["coop-member-tn"]["turns"][0]["TODO_owner"] == "Zainab"

    grievance = by_id["grievance-deposit"]["turns"][0]
    assert grievance["status"] is None and grievance["TODO_owner"] == "Varsha"

    out_of_scope = by_id["out-of-scope-election"]["turns"][0]
    assert out_of_scope["status"] == "declined" and out_of_scope["citations"] is False
    assert out_of_scope["contact_when_declined"] is True
