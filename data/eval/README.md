# Evaluation data

Two small files that let the team measure the real pipeline instead of judging answers by
eye. Nothing here is a source of facts: a question may only come from a verified document,
and an expectation may only name a document id that is in `data/sources.csv`.

## `retrieval_questions.json`: does retrieval find the right document?

Used by `python manage.py eval_retrieval` (inside Docker:
`docker compose exec web python manage.py eval_retrieval`). A JSON list of:

| Field            | Meaning                                                                       |
| ---------------- | ----------------------------------------------------------------------------- |
| `id`             | A unique short name.                                                          |
| `question`       | The question, in English.                                                     |
| `state`          | A state code such as `"TN"`, or `null` for central documents only.            |
| `in_scope`       | `true` if the corpus should answer it, `false` for sports, weather and so on. |
| `expect_doc_ids` | Document ids (from `sources.csv`) that should appear in the top results.      |

Other keys (`TODO_owner`, `source`) are notes and are ignored.

The command prints the top score and document per question, the **hit rate** (in-scope
questions that list `expect_doc_ids`), and a **suggested `SCORE_THRESHOLD`**: halfway
between the 10th percentile of the in-scope top scores and the 90th percentile of the
out-of-scope top scores. It warns when the two ranges overlap or when a group has fewer
than 5 questions. Put the suggestion in `.env`; do not guess the threshold.

**Zainab, to do:** add about 20 in-scope questions with their `expect_doc_ids`, covering
the central Act, the Tamil Nadu Act and rules, the model by-laws, PMFBY, KCC and the
grievance route. Fill in `expect_doc_ids` on the six starter questions (they are marked
`TODO_owner`). Add 5 to 10 more out-of-scope questions. A question with an empty
`expect_doc_ids` still counts toward the threshold, but not toward the hit rate.

### Recording a run for the Quality dashboard

`python manage.py load_test_questions` copies the questions into the database (the
`TestQuestion` table, visible in the admin site). `python manage.py eval_retrieval --record`
does that too, and then saves the run: an `EvalRun` with the settings used (embedding model,
top-k, `SCORE_THRESHOLD`) and one `EvalResult` per question. The staff-only
`GET /api/v1/eval/latest` and the Quality page (`/staff/quality`) then show it.

| Metric          | How it is measured                                                                                                                                               |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hit rate        | In-scope questions that list `expect_doc_ids`: was an expected document retrieved?                                                                               |
| Correct refusal | Out-of-scope questions whose best score is below `SCORE_THRESHOLD`                                                                                               |
| Faithfulness    | **Not measured by any tool.** A person checks answers against their passages and enters the result (`--faithfulness 0.85`, or in the admin site under Eval runs) |

The dashboard shows only a run with all three metrics, so a run without faithfulness waits.
Until a complete run exists it shows clearly labelled sample numbers. A run recorded with
the stub retriever (`--allow-stub`) is always marked as a sample and never shown as real.

## `conversations.json`: does the whole chat behave?

Used by `python scripts/acceptance.py [BASE_URL]` against a running stack (default
`http://localhost`). Each conversation has an `id`, a `title`, an optional `note` and a list
of `turns`; later turns reuse the `conversation_id` returned by the first.

| Turn field              | Meaning                                                            |
| ----------------------- | ------------------------------------------------------------------ |
| `text`, `language`      | The question and its language code (`en`, `hi`, `ta`).             |
| `state`                 | Optional state code.                                               |
| `status`                | `"answered"`, `"declined"`, or `null` to not check.                |
| `citations`             | `true` (at least one), `false` (none), or `null` to not check.     |
| `contact_when_declined` | `true`: a declined answer must carry a contact.                    |
| `must_contain`          | Optional. Strings the answer text must contain (case-insensitive). |
| `expect_doc_ids`        | Optional. At least one of these documents must be cited.           |
| `answer_language_note`  | Free text for the human reader; not checked.                       |

These are always checked, whatever the turn says: a declined answer has no citations and
carries a contact; an answered one has at least one citation.

Open items are marked `TODO_owner`: Zainab (the Tamil Nadu question's `expect_doc_ids`) and
Varsha (what the deposit-grievance question should do). The Tamil question text is
machine-written and needs review by a fluent speaker.

With the stubs on, some turns fail by design: the stub answer does not quote the "72"
deadline, and it treats the word "election" as a by-laws question and asks for a state. Run
the script against the real pipeline (see `docs/running-with-docker.md`).
