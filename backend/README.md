# Sahkar Saathi backend

Django 5.2 + Django Ninja, served by uvicorn (ASGI). This is member A's platform layer from
the Member A plan. Every endpoint in the API contract exists and is frozen in
[`openapi.json`](openapi.json). Answers, retrieval, speech and grievance guidance still
come from **stubs**, so B, C and D can build against the real API before the real
services exist.

## Run it

Requires Python 3.11+ (developed on 3.13; avoid 3.15 for now, as some wheels are missing).

```bash
cd backend
py -3.13 -m venv .venv            # macOS/Linux: python3 -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # local settings; never commit .env
python manage.py migrate          # SQLite by default
python manage.py loaddata sample_documents   # sample library entries (is_sample=true)
uvicorn config.asgi:application --reload --port 8000
```

- API docs: http://127.0.0.1:8000/api/v1/docs (public only when `DJANGO_DEBUG=true`)
- Health: http://127.0.0.1:8000/api/v1/health
- Admin: http://127.0.0.1:8000/admin/ (`python manage.py createsuperuser` first)

**With the React app:** run the backend, then from the repository root run
`VITE_USE_MOCKS=false npm run dev` (PowerShell: `$env:VITE_USE_MOCKS='false'; npm run dev`).
Vite proxies `/api` to port 8000, so there is no CORS setup, just as with Caddy later.

## The API contract (all under `/api/v1/`)

| Method and path               | Purpose                                     | Used by                   | Source today                     |
| ----------------------------- | ------------------------------------------- | ------------------------- | -------------------------------- |
| `GET /health`                 | Deployment check (database, vector store)   | demo checklist            | real                             |
| `GET /meta/languages`         | Options for the language selector           | sidebar                   | settings                         |
| `GET /meta/states`            | States, with the covered one marked         | sidebar                   | settings                         |
| `POST /chat/ask`              | Ask a question in text                      | Ask                       | stub answer service, stored      |
| `POST /speech/transcribe`     | Speech to text (multipart upload)           | Ask, Grievance            | stub speech provider             |
| `POST /speech/synthesize`     | Text to speech (`audio/wav`)                | Ask                       | stub speech provider             |
| `POST /feedback`              | Rate an answer, or send a general comment   | Ask, About                | real, stored                     |
| `GET /grievance/categories`   | Categories for the problem-type chips       | Grievance                 | stub grievance guide             |
| `POST /grievance/guide`       | Category, forum, steps, checklist, draft    | Grievance                 | stub grievance guide             |
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
├── data/            schemes.yaml, lessons.yaml (later forums.yaml, test questions)
├── services/        plain Python, no Django imports
│   ├── types.py     interfaces: Retriever, AnswerService, SpeechProvider, GrievanceGuide
│   ├── stubs.py     stub implementations served while USE_STUBS=true
│   ├── privacy.py   scrub_pii(): removes personal identifiers before storage
│   └── retrieval/ speech/ translation/   real implementations go here (B, C)
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
3. Run with `USE_STUBS=false`. Until step 2 is done, that endpoint returns
   `503 service_not_ready`.
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
| `USE_STUBS`                                                   | everyone | Serve stubs until the real services land (default `true`)               |
| `DEMO_CACHE`                                                  | A, D     | Saved answers for the scripted demo (not wired yet)                     |
| `STORE_MESSAGES`                                              | A        | Turn off to store no question or answer text (metrics are still stored) |
| `REGIONAL_LANGUAGE_*`, `COVERED_STATE_CODE`                   | team     | The third language (default Tamil) and the covered state (default TN)  |
| `CHAT_RATE_LIMIT`, `SPEECH_RATE_LIMIT`, `FEEDBACK_RATE_LIMIT`, `GRIEVANCE_RATE_LIMIT` | A | Per-client limits, e.g. `20/m`                          |
| `LLM_PROVIDER`, `LLM_MODEL`, `BHASHINI_*`                     | C        | Model and speech access                                                 |
| `EMBEDDING_MODEL`, `TOP_K`, `SCORE_THRESHOLD`, `QDRANT_URL`   | B        | Retrieval behaviour                                                     |
| `DATABASE_URL`                                                | A        | PostgreSQL in Compose; SQLite when unset                                |
| `NINJA_NUM_PROXIES`                                           | A        | Set to `1` behind Caddy                                                 |

## Quality checks

```bash
python -m pytest            # 87 tests: every endpoint, error path, storage, privacy, contract
python -m ruff check .
python -m ruff format --check .
python manage.py makemigrations --check --dry-run
```

The same checks, plus the front-end ones, run on every pull request in
`.github/workflows/ci.yml`.

## Not done yet (Member A plan)

- **Sprint 2 models:** GrievanceCase (only when `STORE_MESSAGES` is on), and TestQuestion,
  EvalRun and EvalResult so `/eval/latest` serves real runs instead of sample data.
- **Resilience:** `DEMO_CACHE` (saved answers for the five scripted conversations).
- **Platform:** Docker Compose with PostgreSQL, Qdrant and Caddy; HTTPS demo environment.
- **Real services** from members B and C, plugged in through `config/services.py`.
