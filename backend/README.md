# Sahkar Saathi backend

Django 5.2 + Django Ninja, served by uvicorn (ASGI). This is member A's platform layer from
the Member A plan. Every endpoint in the API contract exists and is frozen in
[`openapi.json`](openapi.json). Every service defaults to a **stub**, so the team can
build against the real API with no network and no model. Retrieval (Qdrant), answers (an
OpenAI-compatible LLM) and speech-to-text (Whisper) can each be switched to the real thing
with their own flag, as can the grievance guide (forums from `services/data/forums.yaml`);
speech synthesis and Bhashini are still stubs.

## Run it

**With Docker (the whole stack):** from the repository root, `docker compose up --build`,
then open http://localhost. See the root README for admin login, HTTPS deployment and the
smoke test. The rest of this section is for running the backend directly while developing.

Requires Python 3.11+ (developed on 3.13; avoid 3.15 for now, as some wheels are missing).

```bash
cd backend
py -3.13 -m venv .venv            # macOS/Linux: python3 -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # local settings; never commit .env
python manage.py migrate          # SQLite by default
python manage.py load_sample_documents   # sample library entries, only into an empty table
uvicorn config.asgi:application --reload --port 8000
```

- API docs: http://127.0.0.1:8000/api/v1/docs (public only when `DJANGO_DEBUG=true`)
- Health: http://127.0.0.1:8000/api/v1/health
- Admin: http://127.0.0.1:8000/admin/ (`python manage.py createsuperuser` first)

**With the React app:** run the backend, then `npm run dev` from the repository root. The
app calls the real API by default; Vite proxies `/api`, `/admin` and `/static` to port
8000, just as Caddy does in Docker, so there is no CORS setup.

### Production mode

`docker-compose.yml` runs the backend with `DJANGO_ENV=production`, which:

- **Requires secrets:** `DJANGO_SECRET_KEY` (or `DJANGO_SECRET_KEY_FILE`), and refuses to
  start without it. DEBUG is always off.
- **Reads secrets from files:** any secret can come from a `*_FILE` path
  (`POSTGRES_PASSWORD_FILE`, `DJANGO_SUPERUSER_PASSWORD_FILE`); Compose generates them.
- **Enables HTTPS mode with `DJANGO_HTTPS=true`:** HSTS (one year), secure session and CSRF
  cookies, and HTTPS redirects. `python manage.py check --deploy` then reports no issues;
  `tests/test_deploy.py` checks this. HSTS preload is a separate opt-in
  (`SECURE_HSTS_PRELOAD`).
- **Shares rate-limit counters:** `CACHE_BACKEND=file` shares them across uvicorn workers.
  Do not use Django's database cache: Ninja checks throttles synchronously inside async
  views, and Django refuses synchronous queries there.

On every start the container runs `migrate`, `collectstatic`, `ensure_superuser` (creates
the team admin once, never resets a password) and, if `LOAD_SAMPLE_DOCUMENTS=true`,
`load_sample_documents`. All are safe to repeat.

## The API contract (all under `/api/v1/`)

| Method and path               | Purpose                                     | Used by                   | Source today                     |
| ----------------------------- | ------------------------------------------- | ------------------------- | -------------------------------- |
| `GET /health`                 | Deployment check (database, vector store)   | demo checklist            | real                             |
| `GET /meta/languages`         | Options for the language selector           | sidebar                   | settings                         |
| `GET /meta/states`            | States, with the covered one marked         | sidebar                   | settings                         |
| `POST /chat/ask`              | Ask a question in text                      | Ask                       | stub, or retriever + LLM (`USE_STUB_ANSWER=false`); stored |
| `POST /speech/transcribe`     | Speech to text (multipart upload)           | Ask, Grievance            | stub, or Whisper (`USE_STUB_SPEECH=false`) |
| `POST /speech/synthesize`     | Text to speech (`audio/wav`)                | Ask                       | stub (silent audio) in both modes |
| `POST /feedback`              | Rate an answer, or send a general comment   | Ask, About                | real, stored                     |
| `GET /grievance/categories`   | Categories for the problem-type chips       | Grievance                 | stub, or `forums.yaml` guide (`USE_STUB_GRIEVANCE=false`) |
| `POST /grievance/guide`       | Category, forum, steps, checklist, draft    | Grievance                 | stub, or `forums.yaml` guide (`USE_STUB_GRIEVANCE=false`) |
| `GET /schemes`                | Scheme cards (`?category=`)                 | Schemes                   | `data/schemes.yaml`              |
| `GET /schemes/{slug}`         | One scheme; `pmfby` has the guide facts     | Schemes, Crop insurance   | `data/schemes.yaml`              |
| `GET /lessons`                | Lessons and the quiz (`?language=`)         | Learn                     | `data/lessons.yaml`              |
| `GET /documents`              | Library (`?state=&type=&language=&include_retired=`) | Library, About   | `Document` table                 |
| `GET /documents/{id}`         | One document                                | Library                   | `Document` table                 |
| `GET /eval/latest`            | Evaluation summary (**staff only**)         | Quality dashboard         | sample data (`is_sample: true`)  |

Field-level details, examples and every error response are in the interactive docs and
`openapi.json`.

**Contract rules**

- Every error has the shape `{"code": "...", "message": "..."}`. Codes: `validation_error`
  (422), `empty_audio` (400), `not_authenticated` (401), `staff_only` (403),
  `message_not_found` / `document_not_found` / `scheme_not_found` / `not_found` (404),
  `audio_too_large` (413), `unsupported_audio_type` (415), `rate_limited` (429, with
  `Retry-After`), `internal_error` (500), `provider_error` (502), `service_not_ready` (503).
- A declined answer has no citations and always names a `contact`; the API layer enforces
  this even if a service gets it wrong.
- Fields the API always sends are required in the contract, even when they can be `null`
  (for example `contact`, `source_url`). Null means "not available", never "omitted".
- Pass the returned `conversation_id` back with follow-up questions; an unknown id starts
  a new conversation. `message_id` is what `POST /feedback` rates.
- Language codes are `en`, `hi` and `REGIONAL_LANGUAGE_CODE` (default `ta`). The covered
  state is `COVERED_STATE_CODE` (default `TN`).
- Public write endpoints are rate-limited per client address, with separate budgets for
  chat, speech, feedback and grievance. This protects free-tier quotas; it is not a
  security control.
- `/eval/latest` uses the Django session from `/admin/`; log in as a staff user first.
- Logs record status and latency, never question, answer or grievance text.

## Changing the contract

The contract is **frozen**. Following the working agreement:

1. Open a pull request and announce it in the team chat. A **breaking** change (removing
   or renaming a field, tightening a type, changing a status code) needs two approvals.
   Adding an optional field or a new endpoint is not breaking.
2. Re-export: `python manage.py export_openapi_schema --api config.api.api --output openapi.json --indent 2`
3. Regenerate the front-end types from the repository root: `npm run gen:api`, then fix
   anything `src/types/contract-check.ts` reports in `npm run build`.

CI fails if `openapi.json` is stale (`tests/test_contract.py`), if `src/types/api.gen.ts`
was not regenerated, or if the UI's types no longer fit the contract.

## What is stored

Every `/chat/ask` call saves an anonymous **Conversation**, a **Message** and its
**Citation** rows, which evaluation and the admin review queue need:

- **Always:** status, `needs_state`, top retrieval score, model name, latency, language,
  state, `document_id`, `is_demo`, and the cited chunks with rank, page and score.
- **Only when `STORE_MESSAGES=true`:** question and answer text, after
  `services/privacy.py` has replaced phone, Aadhaar, PAN, email and long ID numbers with
  placeholders such as `[phone]`.
- **Feedback:** rating, reason and comment (also scrubbed), linked to the Message.

No name, account or IP address is stored. If the database is down, `/chat/ask` still
answers; that exchange just cannot be rated. Grievance descriptions and drafts are not
stored yet (GrievanceCase is a Sprint 2 task).

In the admin (`/admin/`): filter **Feedback** by _Not helpful_ to review weak answers;
add, edit or **retire** (never delete) **Documents**; inspect **Chunks**.

## Content files (`data/`)

Stable facts live in YAML with a source and date, so answers can quote them exactly:

- `schemes.yaml`: scheme cards, plus `facts` for the PMFBY crop insurance guide.
- `lessons.yaml`: lessons and the quiz. Add `lessons.hi.yaml` / `lessons.ta.yaml` for
  translations; the API falls back to English.

They are validated when loaded, and the tests load them, so CI catches mistakes. A scheme
not marked `is_sample`, or a fact not marked `is_placeholder`, **must** have a `source_url`
and date. Never put premium amounts, deadlines or helpline numbers into a placeholder.
Everything in them today is sample content.

## How the code is organised

```text
backend/
├── manage.py
├── config/          settings (all from env), urls, asgi, api.py (NinjaAPI + /health),
│                    errors.py (one error shape), services.py (wiring), throttles.py
├── apps/            Django apps: thin Ninja routers, schemas and models
│   ├── chat/        /chat/ask; Conversation, Message, Citation
│   ├── speech/      /speech/transcribe, /speech/synthesize
│   ├── feedback/    /feedback; Feedback (admin review queue)
│   ├── grievance/   /grievance/categories, /grievance/guide
│   ├── schemes/     /schemes, /schemes/{slug} from data/schemes.yaml
│   ├── lessons/     /lessons from data/lessons*.yaml
│   ├── knowledge/   /documents; Document, Chunk; fixtures/sample_documents.json
│   ├── meta/        /meta/languages, /meta/states
│   └── evaluation/  /eval/latest (staff); sample data until EvalRun models exist
├── data/            schemes.yaml, lessons.yaml (the evaluation questions are in ../data/eval)
├── services/        plain Python, no Django imports
│   ├── types.py     interfaces: Retriever, AnswerService, SpeechProvider, GrievanceGuide
│   ├── stubs.py     stub implementations, served while the matching USE_STUB_* flag is true
│   ├── privacy.py   scrub_pii(): removes personal identifiers before storage
│   ├── llm.py       OpenAI-compatible LLM client (settings read at call time)
│   ├── answer.py    GroundedAnswerService: retrieve, score check, LLM, validated citations
│   ├── retrieval/   QdrantRetriever (embeds the query, searches Qdrant)
│   ├── speech/      WhisperSpeechProvider (speech to text); synthesis is still the stub
│   └── translation/ not started
├── ai/              agent, prompts, RAG, embeddings, safety (C, B). Not started
├── tests/           pytest (pytest-django), including the contract tests
└── openapi.json     the frozen contract
```

**Rule:** handlers import only `services.types` and the wiring functions in
`config/services.py`, never a provider SDK or a service's internals.

## Plugging in a real service (members B and C)

1. Implement the interface from `services/types.py` (for example `SpeechProvider`) in your
   folder, such as `services/speech/bhashini.py`. Keep it free of Django imports, and use
   `async def` with `httpx.AsyncClient` for network calls.
2. In `config/services.py`, replace the `raise ServiceNotReady(...)` line in the matching
   function with your implementation.
3. Turn it on with its own flag (`USE_STUB_RETRIEVER`, `USE_STUB_ANSWER`, `USE_STUB_SPEECH`
   or `USE_STUB_GRIEVANCE` set to `false`); the others stay stubs. Until step 2 is done,
   that endpoint returns `503 service_not_ready`.
4. Raise `services.types.ProviderError` when an upstream call fails; the API turns it into
   a 502 with the standard error shape.

The stubs exercise every state: PMFBY questions are answered with citations; by-law
questions without a state return `needs_state`; a state other than `TN` gives `partial`;
gibberish and out-of-scope questions are declined with a contact. Transcription returns a
fixed sentence, synthesis returns silent WAV audio, and the grievance guide detects a
category by keyword and fills a template draft.

## Settings

All settings come from environment variables; see [`.env.example`](.env.example). These
are the ones the team shares:

| Setting                                                       | Owner    | Purpose                                                                 |
| ------------------------------------------------------------- | -------- | ----------------------------------------------------------------------- |
| `USE_STUBS`                                                   | everyone | Default for every service: serve stubs (default `true`)                 |
| `USE_STUB_RETRIEVER`, `_ANSWER`, `_SPEECH`, `_GRIEVANCE`      | everyone | Override `USE_STUBS` for one service; empty follows `USE_STUBS`         |
| `DEMO_CACHE`                                                  | A, D     | Saved answers for the scripted demo questions (`data/demo_answers.yaml`); also a fallback when a live service fails on one (default `false`) |
| `STORE_MESSAGES`                                              | A        | Turn off to store no question or answer text (metrics are still stored) |
| `REGIONAL_LANGUAGE_*`, `COVERED_STATE_CODE`                   | team     | The third language (default Tamil) and the covered state (default TN)  |
| `CHAT_RATE_LIMIT`, `SPEECH_RATE_LIMIT`, `FEEDBACK_RATE_LIMIT`, `GRIEVANCE_RATE_LIMIT` | A | Per-client limits, e.g. `20/m`                          |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_JSON_MODE` | C | The LLM server (any OpenAI-compatible API); empty values use the defaults |
| `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`     | C        | Speech-to-text; models download into `HF_HOME`                          |
| `HELPLINE_LABEL`, `HELPLINE_DETAIL`                           | C        | Who a declined answer points to (only verified details)                 |
| `BHASHINI_*`                                                  | C        | Not used yet                                                            |
| `EMBEDDING_MODEL`, `TOP_K`, `QDRANT_URL`                      | B        | Retrieval behaviour                                                     |
| `SCORE_THRESHOLD`                                             | B        | Decline below this top score. Set it from `eval_retrieval`, not by guessing |
| `SOURCES_CSV`                                                 | A, B     | The document list for `load_sources` and `ingest_corpus`                |
| `DATABASE_URL`                                                | A        | PostgreSQL in Compose; SQLite when unset                                |
| `NINJA_NUM_PROXIES`                                           | A        | Set to `1` behind Caddy                                                 |

## Management commands and scripts

Run commands from `backend/` (in Docker: `docker compose exec web python manage.py ...`).

| Command                                      | What it does                                                               |
| -------------------------------------------- | -------------------------------------------------------------------------- |
| `load_sources [--dry-run] [--strict]`        | Loads document metadata from `data/sources.csv`; skips and reports bad rows |
| `ingest_corpus`                              | Chunks the PDFs in `data/raw/`, embeds them, writes Chunk rows and Qdrant (needs `requirements-ml.txt`) |
| `corpus_status`                              | Chunks per document, the Qdrant point count, documents with no chunks      |
| `eval_retrieval [--questions] [--top-k]`     | Scores retrieval on `data/eval/retrieval_questions.json`; suggests `SCORE_THRESHOLD` |
| `eval_retrieval --record [--faithfulness X]` | Also saves the run (EvalRun, EvalResult) for the Quality dashboard; see `data/eval/README.md` |
| `load_test_questions [--path]`               | Loads the evaluation questions into the TestQuestion table                 |
| `warm_models`                                | Loads the Whisper and embedding models for the real services (start-up)    |
| `load_sample_documents`, `ensure_superuser`  | Sample library entries (empty table only); the admin account              |
| `python ../scripts/acceptance.py [URL]`      | Runs `data/eval/conversations.json` against a running stack                |
| `python ../scripts/download_pdfs.py`         | Downloads the PDFs with direct links into `data/raw/` (TLS verified)       |
| `python ../scripts/smoke_test.py [URL]`      | 26 checks that the stack is up and locked down                             |

The ML packages are optional for development: without `requirements-ml.txt` everything runs
on the stubs, and the commands that need them say so.

## Quality checks

```bash
python -m pytest            # endpoints, errors, storage, privacy, contract, deploy, pipeline (all faked)
python -m ruff check .
python -m ruff format --check .
python manage.py makemigrations --check --dry-run
```

The same checks, plus the front-end ones, run on every pull request in
`.github/workflows/ci.yml`, which also builds the whole stack with `docker compose up --build`
and runs `scripts/smoke_test.py` against it.

## Not done yet (Member A plan)

- **Sprint 2 models:** GrievanceCase (only when `STORE_MESSAGES` is on). TestQuestion, EvalRun
  and EvalResult are done: `/eval/latest` serves the latest complete run, else sample data.
  Faithfulness is not measured by any tool; staff enter it in the admin site (Eval runs).
- **Resilience:** done (`DEMO_CACHE`). The saved answers for the cooperative-member and
  deposit-grievance questions are placeholders until the owners supply sourced text.
- **Platform:** choose the demo host and test HTTPS from a phone (Compose and Caddy are done).
- **Still stubs:** text to speech (Listen), Bhashini, and asking for a state when the
  question needs one (`needs_state` in the grounded answer service). The grievance guide
  only has recorded forums for crop insurance; `forums.yaml` needs the cooperative routes.
- **Evidence for the real pipeline:** ingest the verified corpus, grow the evaluation
  questions in `data/eval`, and set `SCORE_THRESHOLD` from `eval_retrieval`.
