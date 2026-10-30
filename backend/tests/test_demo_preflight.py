"""scripts/demo_preflight.py against a tiny fake server. No network, no Ollama, no Qdrant,
no Docker: `docker compose` and the memory reader are replaced."""

import importlib.util
import json
import threading
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from django.conf import settings

ROOT = Path(settings.BASE_DIR).parent
SCRIPT = ROOT / "scripts" / "demo_preflight.py"
GIB = 1024**3

CITATION = {"document_id": "DOC-1", "title": "PMFBY guidelines"}
ANSWERS = {
    "en": "Report the loss within 72 hours.",
    "hi": "72 घंटे के भीतर नुकसान की सूचना दें।",
    "ta": "72 மணி நேரத்திற்குள் இழப்பைத் தெரிவிக்கவும்.",
}


def load_script():
    spec = importlib.util.spec_from_file_location("demo_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corpus_output(ingested: int, empty: int = 0, chunks: int | None = None) -> str:
    rows = [f"{'document':<46} {'state':<8} chunks"]
    rows += [f"{'DOC-' + str(n):<46} {'central':<8} 5" for n in range(ingested)]
    rows += [f"{'EMPTY-' + str(n):<46} {'central':<8} 0" for n in range(empty)]
    total = ingested * 5 if chunks is None else chunks
    rows += [
        f"\nDocuments: {ingested + empty}   Chunk rows: {total}",
        f"Qdrant collection 'sahkar_saathi_chunks': {total}",
    ]
    return "\n".join(rows) + "\n"


@pytest.fixture
def stack(monkeypatch):
    """A fake API plus Ollama on one port. Change ``state`` to break things."""
    state = {
        "health": {
            "status": "ok",
            "version": "1.0",
            "stubs": False,
            "database": "ok",
            "vector_store": "ok",
        },  # fmt: skip
        "models": ["llama3.1:8b"],
        "v1_models": True,
        "tags": True,
        "documents": 12,
        "is_demo": False,
        "decline": False,
        "requests": [],
    }

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def do_GET(self):
            if self.path == "/api/v1/health":
                self._send(200, state["health"])
            elif self.path == "/v1/models" and state["v1_models"]:
                self._send(200, {"data": [{"id": m} for m in state["models"]]})
            elif self.path == "/api/tags" and state["tags"]:
                self._send(200, {"models": [{"name": m} for m in state["models"]]})
            elif self.path == "/api/v1/documents":
                self._send(200, [{"id": f"D{n}"} for n in range(state["documents"])])
            else:
                self._send(404, {})

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(payload)
            declined = state["decline"]
            self._send(
                200,
                {
                    "conversation_id": "c1",
                    "message_id": "m1",
                    "answer_text": "Not found." if declined else ANSWERS[payload["language"]],
                    "status": "declined" if declined else "answered",
                    "needs_state": False,
                    "citations": [] if declined else [CITATION],
                    "followups": [],
                    "contact": {"label": "Office", "detail": "x"} if declined else None,
                    "is_demo": state["is_demo"],
                },
            )

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}"
    state["memory"] = 8 * GIB
    yield state
    httpd.shutdown()


def preflight(stack, capsys, monkeypatch, *extra, docker_output=None, docker_code=0):
    """Run main() against the fake stack; returns (exit code, printed output)."""
    module = load_script()
    monkeypatch.setattr(module, "free_memory_bytes", lambda: stack["memory"])
    if docker_output is not None:

        def fake_run(cmd, **kwargs):
            assert cmd[:3] == ["docker", "compose", "exec"] and cmd[-1] == "corpus_status"
            return types.SimpleNamespace(returncode=docker_code, stdout=docker_output, stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)
    argv = [
        stack["url"],
        "--llm-base-url",
        f"{stack['url']}/v1",
        "--llm-model",
        "llama3.1:8b",
        *extra,
    ]
    code = module.main(argv, env={})
    return code, capsys.readouterr().out


def good_run(stack, capsys, monkeypatch, **kwargs):
    return preflight(
        stack, capsys, monkeypatch, "--docker", docker_output=corpus_output(12), **kwargs
    )


def lines(out: str, level: str, name: str) -> list[str]:
    return [ln for ln in out.splitlines() if ln.startswith(level) and f" {name}" in ln[:20]]


# --- the whole run ----------------------------------------------------------------------


def test_everything_ready(stack, capsys, monkeypatch):
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0
    assert out.rstrip().endswith("READY") and "NOT READY" not in out
    for name in ("health", "ollama", "corpus", "chat[en]", "chat[hi]", "chat[ta]", "memory"):
        assert lines(out, "PASS", name), name
    assert "0 failed" in out


def test_the_three_questions_are_en_hi_ta_from_the_conversations_file(stack, capsys, monkeypatch):
    good_run(stack, capsys, monkeypatch)
    assert [r["language"] for r in stack["requests"]] == ["en", "hi", "ta"]
    assert all(r["text"] for r in stack["requests"])


# --- 1 and 2: health and flags ----------------------------------------------------------


def test_a_degraded_health_fails(stack, capsys, monkeypatch):
    stack["health"] = {**stack["health"], "status": "degraded", "vector_store": "unreachable"}
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 1 and "NOT READY" in out
    assert lines(out, "FAIL", "health") and "vector_store=unreachable" in out


def test_an_api_that_is_down_fails_and_skips_the_questions(capsys, monkeypatch, stack):
    stack["url"] = "http://127.0.0.1:9"
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 1 and "NOT READY" in out
    assert lines(out, "FAIL", "health") and "no response" in out
    assert len(lines(out, "FAIL", "chat[")) == 3 and "skipped" in out


def test_a_stub_service_fails_the_flags_check(stack, capsys, monkeypatch):
    stack["health"] = {**stack["health"], "stubs": True}
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 1
    assert lines(out, "FAIL", "flags") and "USE_STUB_ANSWER" in out and "DEMO_CACHE=false" in out


def test_individual_flags_are_reported_as_unverifiable_not_passed(stack, capsys, monkeypatch):
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0  # a WARN never fails the run
    warning = lines(out, "WARN", "flags")
    assert warning and "cannot verify" in warning[0] and "DEMO_CACHE=false" in warning[0]


# --- 3: Ollama --------------------------------------------------------------------------


def test_ollama_that_is_down_fails_with_a_clear_message(stack, capsys, monkeypatch):
    module_args = [stack["url"], "--llm-base-url", "http://127.0.0.1:9/v1"]
    module = load_script()
    monkeypatch.setattr(module, "free_memory_bytes", lambda: 8 * GIB)
    code = module.main(module_args, env={})
    out = capsys.readouterr().out
    assert code == 1 and lines(out, "FAIL", "ollama")
    assert "ollama serve" in out


def test_a_missing_model_fails_and_says_how_to_pull_it(stack, capsys, monkeypatch):
    stack["models"] = ["mistral:7b"]
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 1
    assert "not installed" in out and "ollama pull llama3.1:8b" in out and "mistral:7b" in out


def test_the_native_tags_endpoint_is_the_fallback(stack, capsys, monkeypatch):
    stack["v1_models"] = False
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0 and lines(out, "PASS", "ollama")


def test_model_names_are_matched_with_an_implicit_latest_tag():
    module = load_script()
    assert module.model_installed("llama3.1", ["llama3.1:latest"])
    assert module.model_installed("llama3.1:8b", ["other", "llama3.1:8b"])
    assert not module.model_installed("llama3.1:8b", ["llama3.1:70b"])


def test_llm_settings_order_and_docker_host_rewrite():
    module = load_script()
    args = types.SimpleNamespace(llm_base_url=None, llm_model=None)
    dotenv = {"LLM_BASE_URL": "http://host.docker.internal:11434/v1", "LLM_MODEL": "from-dotenv"}
    env = {"LLM_MODEL": "from-env"}
    assert module.llm_settings(args, env, dotenv) == ("http://localhost:11434/v1", "from-env")
    args = types.SimpleNamespace(llm_base_url="http://other:1/v1/", llm_model="chosen")
    assert module.llm_settings(args, env, dotenv) == ("http://other:1/v1", "chosen")
    args = types.SimpleNamespace(llm_base_url=None, llm_model=None)
    assert module.llm_settings(args, {}, {}) == (module.DEFAULT_LLM_BASE_URL, "llama3.1:8b")


# --- 4: corpus --------------------------------------------------------------------------


def test_parse_corpus_status():
    module = load_script()
    stats = module.parse_corpus_status(corpus_output(3, empty=2))
    assert stats["documents"] == 5 and stats["chunks"] == 15 and stats["ingested"] == 3
    assert stats["qdrant"] == "15" and stats["mismatch"] is False
    assert module.parse_corpus_status("Traceback ...") is None


def test_fewer_than_ten_ingested_documents_warns(stack, capsys, monkeypatch):
    code, out = preflight(
        stack, capsys, monkeypatch, "--docker", docker_output=corpus_output(9, empty=4)
    )
    assert code == 0
    warning = lines(out, "WARN", "corpus")
    assert warning and "9 of 13" in warning[0] and "Fewer than 10" in warning[0]


def test_an_empty_corpus_fails(stack, capsys, monkeypatch):
    code, out = preflight(
        stack, capsys, monkeypatch, "--docker", docker_output=corpus_output(0, empty=3)
    )
    assert code == 1 and "ingest_corpus" in out and lines(out, "FAIL", "corpus")


def test_a_mismatch_between_postgres_and_qdrant_warns(stack, capsys, monkeypatch):
    text = corpus_output(12) + "PostgreSQL has 60 chunk rows but Qdrant has 3 points.\n"
    code, out = preflight(stack, capsys, monkeypatch, "--docker", docker_output=text)
    assert code == 0 and "disagree" in out


def test_corpus_status_that_cannot_run_fails(stack, capsys, monkeypatch):
    code, out = preflight(
        stack, capsys, monkeypatch, "--docker", docker_output="no such service: web", docker_code=1
    )
    assert code == 1 and lines(out, "FAIL", "corpus")


def test_without_docker_the_corpus_check_is_a_warning_that_says_so(stack, capsys, monkeypatch):
    code, out = preflight(stack, capsys, monkeypatch)
    assert code == 0
    warning = lines(out, "WARN", "corpus")
    assert warning and "12 document(s)" in warning[0] and "--docker" in warning[0]


# --- 5: questions -----------------------------------------------------------------------


def test_a_demo_answer_is_a_warning_not_a_failure(stack, capsys, monkeypatch):
    stack["is_demo"] = True
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0
    assert len(lines(out, "WARN", "chat[")) == 3 and "is_demo=true" in out


def test_a_declined_in_scope_question_fails(stack, capsys, monkeypatch):
    stack["decline"] = True
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 1 and lines(out, "FAIL", "chat[en]")
    assert "status is 'declined', expected 'answered'" in out


def test_a_slow_answer_warns(stack, capsys, monkeypatch):
    module = load_script()
    monkeypatch.setattr(module, "SLOW_SECONDS", -1)  # every answer is "slow"
    monkeypatch.setattr(module, "free_memory_bytes", lambda: 8 * GIB)
    code = module.main(
        [stack["url"], "--llm-base-url", f"{stack['url']}/v1", "--llm-model", "llama3.1:8b"],
        env={},
    )
    out = capsys.readouterr().out
    assert code == 0 and "slower than" in out and len(lines(out, "WARN", "chat[")) == 3


# --- 6: memory --------------------------------------------------------------------------


def test_low_memory_warns(stack, capsys, monkeypatch):
    stack["memory"] = 2 * GIB
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0
    warning = lines(out, "WARN", "memory")
    assert warning and "2.0 GB free, below 3 GB" in warning[0]


def test_unreadable_memory_warns(stack, capsys, monkeypatch):
    stack["memory"] = None
    code, out = good_run(stack, capsys, monkeypatch)
    assert code == 0 and "cannot read free memory" in out


def test_free_memory_reader_returns_a_number_or_none():
    value = load_script().free_memory_bytes()
    assert value is None or value > 0
