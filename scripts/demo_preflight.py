#!/usr/bin/env python3
"""One-command preflight for the demo machine: is the real pipeline ready?

    python scripts/demo_preflight.py [BASE_URL] [--docker] [--llm-base-url URL]
                                     [--llm-model NAME] [--file data/eval/conversations.json]
                                     [--min-free-gb 3]

BASE_URL defaults to http://localhost (docker compose). Prints one PASS, WARN or FAIL line
per check and a final READY or NOT READY. Exits 1 if any check FAILed (WARN does not).

1. Health: GET /api/v1/health says "ok" (database up, Qdrant up when retrieval is real).
2. Flags: health reports only whether ANY service is still a stub; that must be false (FAIL
   otherwise). It does not expose each USE_STUB_* flag or DEMO_CACHE, so that part is always
   a WARN telling you what to check in .env. Check 5 is the real proof for DEMO_CACHE.
3. Ollama: LLM_BASE_URL is reachable and LLM_MODEL is installed. The values come from the
   options, then the environment, then the repo's .env, then the compose defaults. A
   host.docker.internal address is replaced by localhost, because this script runs on the host.
4. Corpus: documents and chunks ingested. The API only lists the documents loaded from
   sources.csv (ingested or not), so exact counts need --docker, which runs
   `docker compose exec -T web python manage.py corpus_status`. FAIL if no chunk exists, WARN
   if fewer than 10 documents are ingested. Without --docker this check is a WARN.
5. Questions: one English, one Hindi and one Tamil question from conversations.json go through
   POST /api/v1/chat/ask. Each must meet that turn's expectations (the acceptance.py checks);
   WARN if it took over 30 s or the answer is a demo answer (is_demo=true).
6. Memory: free RAM on this machine, WARN below 3 GB (the LLM and Whisper are large).

It cannot tell whether an answer is correct or fluent, whether the LLM runs on this machine
or another one, or which flags are set; a person still reads the answers. Standard library
only.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CONVERSATIONS = ROOT / "data" / "eval" / "conversations.json"
HTTP_TIMEOUT = 10
SLOW_SECONDS = 30
MIN_DOCUMENTS = 10
LANGUAGES = ("en", "hi", "ta")
DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LLM_MODEL = "llama3.1:8b"  # the docker-compose.yml default
FLAGS_TO_CHECK = (
    "USE_STUBS, USE_STUB_RETRIEVER, USE_STUB_ANSWER, USE_STUB_SPEECH, USE_STUB_GRIEVANCE "
    "(all false) and DEMO_CACHE=false"
)


def _load_acceptance():
    """scripts/acceptance.py by path: ask() (with its rate-limit retry) and check_turn()."""
    path = pathlib.Path(__file__).resolve().parent / "acceptance.py"
    spec = importlib.util.spec_from_file_location("acceptance", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


acceptance = _load_acceptance()


class Report:
    def __init__(self) -> None:
        self.counts = {"PASS": 0, "WARN": 0, "FAIL": 0}

    def line(self, level: str, name: str, detail: str) -> None:
        self.counts[level] += 1
        print(f"{level:<5} {name}: {detail}", flush=True)

    def pass_(self, name: str, detail: str) -> None:
        self.line("PASS", name, detail)

    def warn(self, name: str, detail: str) -> None:
        self.line("WARN", name, detail)

    def fail(self, name: str, detail: str) -> None:
        self.line("FAIL", name, detail)


def get_json(url: str) -> tuple[int, object]:
    """GET a URL. Returns (HTTP status, parsed JSON or None); status 0 means no response."""
    try:
        with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as err:
        return err.code, None
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, None
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, None


# --- 1 and 2: health and flags ---------------------------------------------------------


def check_health(report: Report, base_url: str) -> dict | None:
    status, body = get_json(f"{base_url}/api/v1/health")
    if status == 0:
        report.fail("health", f"no response from {base_url}. Is `docker compose up` running?")
        return None
    if status != 200 or not isinstance(body, dict):
        report.fail("health", f"HTTP {status} from /api/v1/health")
        return None
    detail = (
        f"status={body.get('status')} version={body.get('version')} "
        f"database={body.get('database')} vector_store={body.get('vector_store')}"
    )
    if body.get("status") == "ok":
        report.pass_("health", detail)
    else:
        report.fail("health", f"degraded: {detail}")
    return body


def check_flags(report: Report, health: dict | None) -> None:
    if health is None:
        report.fail("flags", "skipped: the health check did not answer")
        return
    if health.get("stubs") is True:
        report.fail("flags", f"a service is still a stub. Check .env: {FLAGS_TO_CHECK}")
    elif health.get("stubs") is False:
        report.pass_("flags", "no service is a stub (retriever, answer, speech, grievance)")
    else:
        report.warn("flags", "health does not say whether services are stubs")
    report.warn(
        "flags",
        "cannot verify the individual flags or DEMO_CACHE through the API. "
        f"Check .env: {FLAGS_TO_CHECK}. Check 5 shows whether answers are live.",
    )


# --- 3: Ollama --------------------------------------------------------------------------


def read_dotenv(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.split(" #")[0].strip().strip("\"'")
    return values


def llm_settings(args: argparse.Namespace, env: dict[str, str], dotenv: dict[str, str]):
    """(base URL, model): options, then the environment, then .env, then the defaults."""

    def pick(option, name, default):
        return option or env.get(name) or dotenv.get(name) or default

    base = pick(args.llm_base_url, "LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    # Inside the container the host is host.docker.internal; from here it is localhost.
    base = base.replace("host.docker.internal", "localhost")
    return base.rstrip("/"), pick(args.llm_model, "LLM_MODEL", DEFAULT_LLM_MODEL)


def model_installed(model: str, names: list[str]) -> bool:
    return model in names or (":" not in model and f"{model}:latest" in names)


def check_llm(report: Report, base_url: str, model: str) -> None:
    names: list[str] | None = None
    status, body = get_json(f"{base_url}/models")  # OpenAI-compatible (Ollama serves it too)
    if status == 200 and isinstance(body, dict):
        names = [m.get("id", "") for m in body.get("data") or [] if isinstance(m, dict)]
    else:
        native = base_url.removesuffix("/v1")
        status, body = get_json(f"{native}/api/tags")
        if status == 200 and isinstance(body, dict):
            names = [m.get("name", "") for m in body.get("models") or [] if isinstance(m, dict)]
    if names is None:
        report.fail(
            "ollama",
            f"no answer from {base_url}. Start Ollama (`ollama serve`), or set LLM_BASE_URL.",
        )
    elif model_installed(model, names):
        report.pass_("ollama", f"{base_url} is up and model {model!r} is installed")
    else:
        shown = ", ".join(names[:6]) or "none"
        report.fail(
            "ollama", f"{base_url} is up but model {model!r} is not installed ({shown}). "
            f"Run `ollama pull {model}`."
        )  # fmt: skip


# --- 4: corpus --------------------------------------------------------------------------


def parse_corpus_status(text: str) -> dict | None:
    """Documents, chunk rows and ingested documents from `manage.py corpus_status`."""
    totals = re.search(r"Documents:\s*(\d+)\s+Chunk rows:\s*(\d+)", text)
    if not totals:
        return None
    rows = re.findall(r"^([\w.\-]+)\s+(\S+)\s+(\d+)\s*$", text, re.M)
    points = re.search(r"Qdrant collection '[^']*':\s*(.+)", text)
    return {
        "documents": int(totals.group(1)),
        "chunks": int(totals.group(2)),
        "ingested": sum(int(count) > 0 for _, _, count in rows),
        "qdrant": points.group(1).strip() if points else "unknown",
        "mismatch": "PostgreSQL has" in text,
    }


def run_corpus_status() -> tuple[int, str]:
    try:
        done = subprocess.run(
            ["docker", "compose", "exec", "-T", "web", "python", "manage.py", "corpus_status"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120, check=False,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired) as err:
        return 1, str(err)
    return done.returncode, done.stdout + done.stderr


def check_corpus(report: Report, base_url: str, use_docker: bool) -> None:
    if not use_docker:
        status, body = get_json(f"{base_url}/api/v1/documents")
        if isinstance(body, list):
            listed = f"the API lists {len(body)} document(s), but that is the sources.csv list"
        else:
            listed = "the API gave no document list, and its list would only be sources.csv"
        report.warn(
            "corpus",
            f"{listed}, ingested or not. Chunk and ingested document counts need --docker "
            "(runs manage.py corpus_status in the container).",
        )
        return
    code, output = run_corpus_status()
    stats = parse_corpus_status(output) if code == 0 else None
    if stats is None:
        reason = output.strip().splitlines()[-1] if output.strip() else "no output"
        report.fail("corpus", f"corpus_status did not run ({reason}). Is the stack up?")
        return
    detail = (
        f"{stats['ingested']} of {stats['documents']} document(s) have chunks, "
        f"{stats['chunks']} chunk row(s), Qdrant {stats['qdrant']}"
    )
    if stats["chunks"] == 0:
        report.fail("corpus", f"{detail}. Nothing is ingested: run `manage.py ingest_corpus`.")
    elif stats["ingested"] < MIN_DOCUMENTS:
        report.warn("corpus", f"{detail}. Fewer than {MIN_DOCUMENTS} documents are ingested.")
    else:
        report.pass_("corpus", detail)
    if stats["mismatch"]:
        report.warn("corpus", "PostgreSQL and Qdrant disagree: run ingest_corpus again")


# --- 5: questions -----------------------------------------------------------------------


def pick_questions(path: pathlib.Path) -> list[dict]:
    """The first turn in each of en, hi and ta from the conversations file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        raise SystemExit(f"Cannot read {path}: {err}") from err
    chosen: dict[str, dict] = {}
    for conversation in data if isinstance(data, list) else []:
        for turn in conversation.get("turns") or []:
            chosen.setdefault(turn.get("language", "en"), turn)
    missing = [lang for lang in LANGUAGES if lang not in chosen]
    if missing:
        raise SystemExit(f"{path} has no question in: {', '.join(missing)}")
    return [chosen[lang] for lang in LANGUAGES]


def check_questions(report: Report, base_url: str, turns: list[dict], api_up: bool) -> None:
    for turn in turns:
        language = turn.get("language", "en")
        name = f"chat[{language}]"
        if not api_up:
            report.fail(name, "skipped: the API did not answer the health check")
            continue
        payload = {"text": turn["text"], "language": language}
        if turn.get("state"):
            payload["state"] = turn["state"]
        started = time.perf_counter()
        status, body = acceptance.ask(base_url, payload)
        seconds = time.perf_counter() - started
        problems = acceptance.check_turn(turn, status, body)
        cited = len(body.get("citations") or []) if status == 200 else 0
        detail = f"{body.get('status') if status == 200 else 'no answer'}, {cited} citation(s), "
        detail += f"{seconds:.1f} s"
        if problems:
            report.fail(name, f"{detail}: {'; '.join(problems)}")
            continue
        notes = []
        if body.get("is_demo") is True:
            notes.append("demo answer (is_demo=true): DEMO_CACHE or a stub, not the live pipeline")
        if seconds > SLOW_SECONDS:
            notes.append(f"slower than {SLOW_SECONDS} s: warm the models first")
        if notes:
            report.warn(name, f"{detail}; {'; '.join(notes)}")
        else:
            report.pass_(name, detail)


# --- 6: memory --------------------------------------------------------------------------


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
        ("avail_extended", ctypes.c_ulonglong),
    ]  # fmt: skip


def free_memory_bytes() -> int | None:
    """Memory available to new programs on this machine, or None if it cannot be read."""
    system = platform.system()
    try:
        if system == "Linux":
            for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
        elif system == "Windows":
            status = _MemoryStatus()
            status.length = ctypes.sizeof(_MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.avail_phys)
        elif system == "Darwin":
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
            size = int(re.search(r"page size of (\d+)", out).group(1))
            pages = sum(
                int(m.group(1))
                for m in re.finditer(r"Pages (?:free|inactive|speculative):\s+(\d+)", out)
            )
            return pages * size
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None
    return None


def check_memory(report: Report, min_free_gb: float) -> None:
    free = free_memory_bytes()
    if free is None:
        report.warn("memory", f"cannot read free memory on {platform.system()}; check by hand")
        return
    gigabytes = free / 1024**3
    if gigabytes < min_free_gb:
        report.warn(
            "memory",
            f"{gigabytes:.1f} GB free, below {min_free_gb:g} GB. Close other programs, or "
            "use a smaller LLM_MODEL and WHISPER_MODEL.",
        )
    else:
        report.pass_("memory", f"{gigabytes:.1f} GB free")


def main(argv: list[str] | None = None, env: dict[str, str] | None = None) -> int:
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Preflight check for the demo machine.")
    parser.add_argument("base_url", nargs="?", default="http://localhost")
    parser.add_argument("--docker", action="store_true", help="Count chunks via corpus_status.")
    parser.add_argument("--llm-base-url", help="Default: LLM_BASE_URL, .env, then Ollama here.")
    parser.add_argument("--llm-model", help=f"Default: LLM_MODEL, .env, then {DEFAULT_LLM_MODEL}.")
    parser.add_argument("--file", type=pathlib.Path, default=DEFAULT_CONVERSATIONS)
    parser.add_argument("--min-free-gb", type=float, default=3.0)
    args = parser.parse_args(argv)

    base_url = args.base_url.rstrip("/")
    turns = pick_questions(args.file)
    llm_url, llm_model = llm_settings(
        args, dict(os.environ if env is None else env), read_dotenv(ROOT / ".env")
    )
    report = Report()
    print(f"Demo preflight against {base_url}\n", flush=True)

    health = check_health(report, base_url)
    check_flags(report, health)
    check_llm(report, llm_url, llm_model)
    check_corpus(report, base_url, args.docker)
    check_questions(report, base_url, turns, api_up=health is not None)
    check_memory(report, args.min_free_gb)

    counts = report.counts
    ready = counts["FAIL"] == 0
    print(f"\n{counts['PASS']} passed, {counts['WARN']} warning(s), {counts['FAIL']} failed.")
    print("READY" if ready else "NOT READY")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
