"""Evaluation models: TestQuestion, EvalRun, EvalResult; GET /eval/latest serving the latest
complete real run (sample data otherwise); load_test_questions; eval_retrieval --record."""

import io
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.evaluation import models as eval_models
from apps.evaluation.recording import Outcome, record_run
from apps.knowledge.management.commands import eval_retrieval as eval_module
from services.types import Passage

URL = "/api/v1/eval/latest"
QUESTION_FILE = Path(__file__).resolve().parents[2] / "data" / "eval" / "retrieval_questions.json"


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_user("staff", password="pw-for-tests", is_staff=True)
    client.force_login(user)
    return user


def question(qid, in_scope=True, expect=None, state=None, text=None):
    return {
        "id": qid,
        "question": text or f"Question {qid}?",
        "state": state,
        "in_scope": in_scope,
        "expect_doc_ids": expect or [],
    }


def outcome(q, score, doc="DOC-A", hit=None):
    return Outcome(q, score, doc if score is not None else "", hit)


def complete_run(**overrides):
    """A recorded run with all three metrics: 2 of 3 expected hits, 1 of 2 refusals."""
    outcomes = [
        outcome(question("in-hit", expect=["DOC-A"]), 0.8, "DOC-A", True),
        outcome(question("in-hit-2", expect=["DOC-A"]), 0.7, "DOC-A", True),
        outcome(question("in-miss", expect=["DOC-A"]), 0.6, "DOC-B", False),
        outcome(question("out-ok", in_scope=False), 0.2),
        outcome(question("out-bad", in_scope=False), 0.7),
    ]
    options = {
        "label": "Test run",
        "embedding_model": "test-embedding",
        "top_k": 4,
        "threshold": 0.5,
        "faithfulness": 0.9,
    } | overrides
    return record_run(outcomes, **options)


def shape(value):
    """The structure of a JSON value: object keys recursively, one sample list element."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


# --- /eval/latest ---------------------------------------------------------------------


def test_without_runs_the_sample_data_is_served(client, staff):
    body = client.get(URL).json()
    assert body["is_sample"] is True
    assert body["latest"]["id"].startswith("run-sample-")


def test_a_complete_real_run_is_served_with_the_contract_shape(client, staff):
    sample_shape = shape(client.get(URL).json())
    run = complete_run()

    body = client.get(URL).json()
    assert body["is_sample"] is False
    assert shape(body) == {**sample_shape, "failed_questions": sample_shape["failed_questions"]}
    assert body["latest"] == {
        "id": f"run-{run.pk}",
        "run_at": body["latest"]["run_at"],
        "label": "Test run",
        "config": {
            "embedding_model": "test-embedding",
            "llm": "n/a (retrieval only)",
            "top_k": 4,
            "threshold": 0.5,
            "prompt_version": "n/a (retrieval only)",
        },
        "hit_rate": pytest.approx(2 / 3),
        "faithfulness": 0.9,
        "correct_refusal": 0.5,
        "questions": 5,
    }
    metrics = {m["key"]: m for m in body["metrics"]}
    assert set(metrics) == {"hit_rate", "faithfulness", "correct_refusal"}
    assert metrics["hit_rate"]["value"] == pytest.approx(2 / 3)
    assert metrics["hit_rate"]["target"] == 0.85
    assert "top 4 results, over 3 questions" in metrics["hit_rate"]["description"]
    assert "2 out-of-scope questions" in metrics["correct_refusal"]["description"]


def test_failed_questions_come_from_the_results(client, staff):
    complete_run()
    failed = {f["id"]: f for f in client.get(URL).json()["failed_questions"]}
    assert set(failed) == {"in-miss", "out-bad"}
    assert failed["in-miss"]["failure"] == "retrieval-miss"
    assert failed["in-miss"]["question"] == "Question in-miss?" and failed["in-miss"]["language"]
    assert "DOC-A" in failed["in-miss"]["note"] and "DOC-B" in failed["in-miss"]["note"]
    assert failed["out-bad"]["failure"] == "should-decline"


def test_runs_are_oldest_first_and_the_latest_is_the_newest(client, staff):
    now = timezone.now()
    first = complete_run(label="First", run_at=now - timedelta(days=2))
    third = complete_run(label="Third", run_at=now)
    second = complete_run(label="Second", run_at=now - timedelta(days=1))
    body = client.get(URL).json()
    assert [r["label"] for r in body["runs"]] == ["First", "Second", "Third"]
    assert body["latest"]["id"] == f"run-{third.pk}" == body["runs"][-1]["id"]
    assert {first.pk, second.pk} < {int(r["id"].removeprefix("run-")) for r in body["runs"]}


def test_only_the_ten_most_recent_runs_are_listed(client, staff):
    now = timezone.now()
    for n in range(12):
        complete_run(label=f"Run {n}", run_at=now + timedelta(hours=n))
    body = client.get(URL).json()
    assert len(body["runs"]) == 10 and body["latest"]["label"] == "Run 11"
    assert body["runs"][0]["label"] == "Run 2"


def test_a_run_without_faithfulness_waits_and_the_previous_run_stays(client, staff):
    kept = complete_run(label="Complete", run_at=timezone.now() - timedelta(days=1))
    waiting = complete_run(label="Waiting", faithfulness=None)
    assert waiting.is_complete is False
    body = client.get(URL).json()
    assert body["latest"]["id"] == f"run-{kept.pk}"

    # Once someone enters faithfulness in the admin site, it becomes the latest.
    waiting.faithfulness = 0.8
    waiting.save()
    assert client.get(URL).json()["latest"]["id"] == f"run-{waiting.pk}"


def test_with_only_an_incomplete_run_the_sample_data_is_served(client, staff):
    complete_run(faithfulness=None)
    assert client.get(URL).json()["is_sample"] is True


def test_a_run_marked_as_a_sample_is_never_served_as_real(client, staff):
    complete_run(is_sample=True)
    assert client.get(URL).json()["is_sample"] is True


def test_a_run_with_no_failures_has_an_empty_failed_list(client, staff):
    record_run(
        [
            outcome(question("ok", expect=["DOC-A"]), 0.9, "DOC-A", True),
            outcome(question("declined", in_scope=False), 0.1),
        ],
        label="Clean",
        embedding_model="e",
        top_k=4,
        threshold=0.5,
        faithfulness=1.0,
    )
    body = client.get(URL).json()
    assert body["is_sample"] is False and body["failed_questions"] == []
    assert body["latest"]["hit_rate"] == 1.0 and body["latest"]["correct_refusal"] == 1.0


def test_a_run_that_cannot_measure_correct_refusal_is_incomplete(client, staff):
    run = record_run(
        [outcome(question("ok", expect=["DOC-A"]), 0.9, "DOC-A", True)],
        label="No out-of-scope questions",
        embedding_model="e",
        top_k=4,
        threshold=0.5,
        faithfulness=1.0,
    )
    assert run.correct_refusal is None and run.is_complete is False
    assert client.get(URL).json()["is_sample"] is True


def test_access_rules_are_unchanged(client):
    complete_run()
    assert client.get(URL).status_code == 401
    user = get_user_model().objects.create_user("member", password="pw-for-tests")
    client.force_login(user)
    res = client.get(URL)
    assert res.status_code == 403 and res.json()["code"] == "staff_only"


# --- record_run -----------------------------------------------------------------------


def test_metrics_are_none_when_they_cannot_be_measured():
    only_in = record_run(
        [outcome(question("a"), 0.9, "DOC-A", None)],
        label="x",
        embedding_model="e",
        top_k=4,
        threshold=0.5,
    )
    assert only_in.hit_rate is None and only_in.correct_refusal is None
    assert only_in.faithfulness is None and only_in.question_count == 1


def test_an_out_of_scope_question_with_no_passages_counts_as_refused():
    run = record_run(
        [Outcome(question("out", in_scope=False), None, "", None)],
        label="x",
        embedding_model="e",
        top_k=4,
        threshold=0.5,
    )
    assert run.correct_refusal == 1.0
    assert not run.results.get().failure


def test_the_threshold_boundary_matches_the_answer_service():
    """The answer service declines below the threshold, so a score equal to it is not a refusal."""
    run = record_run(
        [outcome(question("out", in_scope=False), 0.5)],
        label="x",
        embedding_model="e",
        top_k=4,
        threshold=0.5,
    )
    assert run.correct_refusal == 0.0
    assert run.results.get().failure == "should-decline"


def test_results_are_saved_per_question():
    run = complete_run()
    assert run.results.count() == 5 and eval_models.TestQuestion.objects.count() == 5
    miss = run.results.get(question_id="in-miss")
    assert (miss.top_score, miss.top_document_id, miss.hit) == (0.6, "DOC-B", False)


def test_metric_values_must_be_between_zero_and_one():
    from django.core.exceptions import ValidationError

    run = complete_run()
    run.faithfulness = 1.5
    with pytest.raises(ValidationError):
        run.full_clean()


# --- load_test_questions --------------------------------------------------------------


def load(*args):
    out = io.StringIO()
    call_command("load_test_questions", *args, stdout=out)
    return out.getvalue()


def test_loads_the_committed_question_file_and_is_idempotent():
    questions = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    out = load()
    assert f"{len(questions)} questions" in out and f"created {len(questions)}" in out
    assert eval_models.TestQuestion.objects.count() == len(questions)
    assert eval_models.TestQuestion.objects.filter(in_scope=False).count() == sum(
        not q["in_scope"] for q in questions
    )
    assert "created 0, updated 0" in load()


def test_an_edited_question_is_updated_and_other_rows_are_left_alone(tmp_path):
    path = tmp_path / "q.json"
    path.write_text(json.dumps([question("a", text="Old text?"), question("b")]), encoding="utf-8")
    load("--path", str(path))
    eval_models.TestQuestion.objects.create(id="admin-added", question="Added?", in_scope=True)

    path.write_text(
        json.dumps([question("a", text="New text?", expect=["DOC-1"], state="TN"), question("b")]),
        encoding="utf-8",
    )
    out = load("--path", str(path))
    assert "created 0, updated 1, unchanged 1" in out
    assert "1 other question(s)" in out
    row = eval_models.TestQuestion.objects.get(pk="a")
    assert (row.question, row.expect_doc_ids, row.state) == ("New text?", ["DOC-1"], "TN")
    assert eval_models.TestQuestion.objects.filter(pk="admin-added").exists()


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "not valid JSON"),
        ("[]", "non-empty JSON list"),
        ('[{"id": "a b", "question": "q", "in_scope": true}]', "must be a slug"),
        ('[{"id": "a", "question": "q", "in_scope": true, "state": "TOOLONGSTATE"}]', "state"),
    ],
)
def test_a_bad_question_file_is_a_clear_error(tmp_path, content, message):
    path = tmp_path / "q.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(CommandError, match=message):
        load("--path", str(path))
    assert not eval_models.TestQuestion.objects.exists()


# --- eval_retrieval --record ----------------------------------------------------------


class FakeRetriever:
    def __init__(self, script):
        self.script = script  # question text -> (score, document id)

    async def search(self, query, *, state, language, top_k=4, document_id=None):
        score, doc = self.script[query]
        return [
            Passage(
                chunk_id="c",
                text="t",
                document_id=doc,
                document_title=doc,
                publisher="p",
                source_url=None,
                published_date=None,
                page=1,
                score=score,
                state=None,
            )
        ]


def run_record(monkeypatch, tmp_path, *args, stub=False, settings=None):
    questions = [
        question("in-1", expect=["DOC-A"]),
        question("in-2", expect=["DOC-A"]),
        question("out-1", in_scope=False),
    ]
    script = {
        "Question in-1?": (0.8, "DOC-A"),
        "Question in-2?": (0.7, "DOC-X"),
        "Question out-1?": (0.3, "DOC-B"),
    }
    path = tmp_path / "q.json"
    path.write_text(json.dumps(questions), encoding="utf-8")
    monkeypatch.setattr(eval_module, "get_retriever", lambda: FakeRetriever(script))
    settings.USE_STUB_RETRIEVER = stub
    settings.SCORE_THRESHOLD = 0.5
    settings.EMBEDDING_MODEL = "test/embedding"
    out = io.StringIO()
    call_command("eval_retrieval", "--questions", str(path), *args, stdout=out)
    return out.getvalue()


def test_without_record_nothing_is_saved(monkeypatch, tmp_path, settings):
    run_record(monkeypatch, tmp_path, settings=settings)
    assert not eval_models.EvalRun.objects.exists()
    assert not eval_models.TestQuestion.objects.exists()


def test_record_saves_the_run_questions_and_results(monkeypatch, tmp_path, settings):
    out = run_record(
        monkeypatch, tmp_path, "--record", "--label", "My run", "--top-k", "3", settings=settings
    )
    run = eval_models.EvalRun.objects.get()
    assert (run.label, run.top_k, run.threshold, run.embedding_model) == (
        "My run",
        3,
        0.5,
        "test/embedding",
    )
    assert run.hit_rate == 0.5 and run.correct_refusal == 1.0 and run.faithfulness is None
    assert run.question_count == 3 and run.is_sample is False and run.is_complete is False
    assert eval_models.TestQuestion.objects.count() == 3
    assert run.results.get(question_id="in-2").failure == "retrieval-miss"
    assert (
        f"Recorded run-{run.pk}: hit rate 0.50, correct refusal 1.00, faithfulness not measured"
        in out
    )
    assert "all three metrics are set" in out, "it says why the dashboard keeps its old run"


def test_record_with_faithfulness_goes_straight_to_the_dashboard(
    monkeypatch, tmp_path, settings, client
):
    staff = get_user_model().objects.create_user("staff", password="pw-for-tests", is_staff=True)
    client.force_login(staff)
    out = run_record(monkeypatch, tmp_path, "--record", "--faithfulness", "0.85", settings=settings)
    assert "latest run on the Quality dashboard" in out
    body = client.get(URL).json()
    assert body["is_sample"] is False and body["latest"]["faithfulness"] == 0.85


@pytest.mark.parametrize("value", ["1.5", "-0.1"])
def test_record_rejects_a_faithfulness_outside_zero_to_one(monkeypatch, tmp_path, settings, value):
    with pytest.raises(CommandError, match="between 0 and 1"):
        run_record(monkeypatch, tmp_path, "--record", "--faithfulness", value, settings=settings)
    assert not eval_models.EvalRun.objects.exists()


def test_record_refuses_the_stub_retriever(monkeypatch, tmp_path, settings):
    with pytest.raises(CommandError, match="Refusing to record"):
        run_record(monkeypatch, tmp_path, "--record", stub=True, settings=settings)
    assert not eval_models.EvalRun.objects.exists()


def test_a_stub_run_can_be_recorded_but_is_marked_as_a_sample(
    monkeypatch, tmp_path, settings, client
):
    staff = get_user_model().objects.create_user("staff", password="pw-for-tests", is_staff=True)
    client.force_login(staff)
    out = run_record(
        monkeypatch,
        tmp_path,
        "--record",
        "--allow-stub",
        "--faithfulness",
        "0.9",
        stub=True,
        settings=settings,
    )
    run = eval_models.EvalRun.objects.get()
    assert run.is_sample is True and "stub" in run.notes
    assert "marked as a sample" in out
    assert client.get(URL).json()["is_sample"] is True, "never served as a real result"


def test_the_shared_loader_is_still_available_from_eval_retrieval():
    assert eval_module.load_questions(QUESTION_FILE)


# --- Admin ----------------------------------------------------------------------------


def test_the_models_are_registered_in_the_admin_site():
    for model in (eval_models.TestQuestion, eval_models.EvalRun, eval_models.EvalResult):
        assert admin.site.is_registered(model)


def test_the_admin_pages_load(client):
    admin_user = get_user_model().objects.create_superuser("root", password="pw-for-tests")
    client.force_login(admin_user)
    run = complete_run()
    for path in (
        "/admin/evaluation/evalrun/",
        f"/admin/evaluation/evalrun/{run.pk}/change/",
        "/admin/evaluation/testquestion/",
        "/admin/evaluation/evalresult/",
    ):
        assert client.get(path).status_code == 200, path
