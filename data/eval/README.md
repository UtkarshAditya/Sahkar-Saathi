# Evaluation data

Two small files that let the team measure the real pipeline instead of judging answers by
eye. Nothing here is a source of facts: a question may only come from a verified document,
and an expectation may only name a document id that is in `data/sources.csv`.

> **PDFs and git.** The source PDFs in `data/raw/` are what the questions below are
> answered from. Some are tracked in git (added with `git add -f`), but `data/raw/*` is
> still ignored, so a new PDF needs `git add -f` to be shared. Check what is actually there
> with `python manage.py corpus_status --files`.

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
| `answer_script`         | Optional: `"Tamil"`, `"Devanagari"` or `"Latin"`. See below.       |
| `answer_language_note`  | Free text for the human reader; not checked.                       |

These are always checked, whatever the turn says: a declined answer has no citations and
carries a contact; an answered one has at least one citation.

**`answer_script`** checks that the answer is really in the language asked for, which the
other fields cannot. It fails the turn if the answer is empty, if fewer than half of its
letters (with their vowel signs) are in that script's Unicode block (`Tamil` is U+0B80 to
U+0BFF, `Devanagari` U+0900 to U+097F), or if the answer contains the question text
(ignoring case, spacing and the final punctuation). A few Latin acronyms such as PMFBY are
fine. It stops at the script: it cannot judge whether the sentences are fluent or correct,
so a fluent speaker still has to read the answer. A script name the script does not know
stops the run before any question is asked. Only the Tamil PMFBY turn uses it so far; the
Hindi turn could take `"Devanagari"`.

**The deposit turn** expects a clean decline, and its `note` says why: in the ingested
documents no provision says when or how a Tamil Nadu society must return a member's
deposit. Section 29 of the Tamil Nadu Act covers a member's share or interest in capital
(not deposits), and the Ombudsman route for deposit complaints is for multi-State societies
only. If a document is added that covers deposits, change the turn to `"answered"` and
require its section number in `must_contain`, copied from the document.

Open items are marked `TODO_owner`: Zainab (the Tamil Nadu cooperative question's
`expect_doc_ids`). The Tamil question text is machine-written and needs review by a fluent
speaker.

### Live answers and demo answers

Every answer says whether it is a demo answer (`is_demo`): true for the stubs and for the
saved answers of `DEMO_CACHE=true`, false for the live pipeline. The script reports which
is which, because a passing run on saved answers proves nothing about retrieval or the LLM:

| Line   | Meaning                                                                                   |
| ------ | ----------------------------------------------------------------------------------------- |
| `PASS` | A live answer that meets every expectation.                                               |
| `DEMO` | A demo answer (cache or stub). It counts as a **failure** unless `--allow-demo` is given. |
| `FAIL` | An expectation is not met, or there was no answer.                                        |

The summary says how many answers were live, how many were demo and how many turns got no
answer at all. **With `DEMO_CACHE=true`, a run without `--allow-demo` fails by design.** To
check the live pipeline, set `DEMO_CACHE=false` (and `USE_STUB_RETRIEVER=false`,
`USE_STUB_ANSWER=false`) in `.env`, recreate the API container with `docker compose up -d`,
and run `python scripts/acceptance.py`. Use `--allow-demo` only to rehearse the demo itself;
`scripts/demo_smoke.py` does that check and labels cached answers "demo answer, not live".

With the stubs on, some turns also fail on their own expectations: the stub answer does not
quote the "72" deadline, and it treats the word "election" as a by-laws question and asks
for a state.
