# Sahkar Saathi backend

Django 5.2 + Django Ninja, served by uvicorn (ASGI). This is member A's platform layer from
the Member A plan. Today it serves **stub** answers and speech, so B, C and D can build
against the real API before the real services exist.

## Run it

Requires Python 3.11+ (developed on 3.13; avoid 3.15 for now, as some wheels are missing).

```bash
cd backend
py -3.13 -m venv .venv            # macOS/Linux: python3 -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # local settings; never commit .env
python manage.py migrate          # SQLite by default; tables for the admin site
uvicorn config.asgi:application --reload --port 8000
```

- API docs: http://127.0.0.1:8000/api/v1/docs (public only when `DJANGO_DEBUG=true`)
- Health: http://127.0.0.1:8000/api/v1/health
- Admin: http://127.0.0.1:8000/admin/ (`python manage.py createsuperuser` first)

**With the React app:** run the backend, then from the repository root run
`VITE_USE_MOCKS=false npm run dev` (PowerShell: `$env:VITE_USE_MOCKS='false'; npm run dev`).
Vite proxies `/api` to port 8000, so there is no CORS setup, just as with Caddy later.

## Endpoints (all under `/api/v1/`)

| Method and path           | Purpose                                   | In                                                                  | Out                                                                                                                                                           |
| ------------------------- | ----------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /chat/ask`          | Ask a question in text                    | JSON: `text`, `language`, `state`, `conversation_id`, `document_id` | `conversation_id`, `message_id`, `answer_text`, `status` (`answered`/`partial`/`declined`), `needs_state`, `citations[]`, `followups[]`, `contact`, `is_demo` |
| `POST /speech/transcribe` | Speech to text                            | multipart: `audio` file, `language_hint`                            | `text`, `language`, `confidence`, `is_demo`                                                                                                                   |
| `POST /speech/synthesize` | Text to speech                            | JSON: `text`, `language`                                            | `audio/wav` (16 kHz mono)                                                                                                                                     |
| `POST /feedback`          | Rate an answer, or send a general comment | JSON: `message_id`, `rating` (`up`/`down`), `reason`, `comment`     | `201` with `id`, `ok`                                                                                                                                         |
| `GET /health`             | Deployment check                          |                                                                     | `status` (`ok`/`degraded`), `version`, `stubs`, `database`                                                                                                    |

**Contract rules**

- A declined answer has no citations and always names a `contact`. The API layer enforces
  this even if a service gets it wrong.
- Every error has the shape `{"code": "...", "message": "..."}`. The codes are:
  `validation_error` (422), `unsupported_audio_type` (415), `audio_too_large` (413),
  `empty_audio` (400), `message_not_found` (404), `rate_limited` (429, with
  `Retry-After`), `service_not_ready` (503), `provider_error` (502), `internal_error` (500).
- Pass the returned `conversation_id` back with follow-up questions. An unknown id
  starts a new conversation. `message_id` is what `POST /feedback` rates.
- A rating needs a `message_id`; a general comment (About page) needs only `comment`.
- Language codes are `en`, `hi` and `REGIONAL_LANGUAGE_CODE` (default `ta`).
- Audio uploads are checked for type and size (`SPEECH_MAX_UPLOAD_BYTES`, default 5 MB)
  before they are read.
- Logs record status and latency, never question or answer text.
- Public endpoints are rate-limited per client address, with separate budgets for chat,
  speech and feedback (`CHAT_RATE_LIMIT`, `SPEECH_RATE_LIMIT`, `FEEDBACK_RATE_LIMIT`).
  This protects free-tier quotas; it is not a security control.

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
answers; that exchange just cannot be rated.

In the admin (`/admin/`), filter **Feedback** by _Not helpful_ to review weak answers.
Messages are read-only there.

The machine-readable contract is [`openapi.json`](openapi.json). Re-export it after any
schema change:

```bash
python manage.py export_openapi_schema --api config.api.api --output openapi.json --indent 2
```

## How the code is organised

```text
backend/
├── manage.py
├── config/          settings (all from env), urls, asgi, api.py (NinjaAPI),
│                    errors.py (one error shape), services.py (wiring functions),
│                    throttles.py (rate limits)
├── apps/            Django apps: thin Ninja routers and (later) models
│   ├── chat/        POST /chat/ask; Conversation, Message, Citation models + admin
│   ├── feedback/    POST /feedback; Feedback model + admin review queue
│   ├── speech/      POST /speech/transcribe, /speech/synthesize
│   └── knowledge/ grievance/ schemes/ lessons/ evaluation/   (not started)
├── services/        plain Python, no Django imports
│   ├── types.py     the interfaces: Retriever, AnswerService, SpeechProvider, + dataclasses
│   ├── stubs.py     stub implementations served while USE_STUBS=true
│   ├── privacy.py   scrub_pii(): removes personal identifiers before storage
│   └── retrieval/ speech/ translation/   real implementations go here (B, C)
├── ai/              agent, prompts, RAG, embeddings, safety (C, B). Not started
└── tests/           pytest (pytest-django)
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
fixed sentence, and synthesis returns silent WAV audio.

## Settings

All settings come from environment variables; see [`.env.example`](.env.example). These
are the ones the team shares:

| Setting                                                       | Owner    | Purpose                                                                 |
| ------------------------------------------------------------- | -------- | ----------------------------------------------------------------------- |
| `USE_STUBS`                                                   | everyone | Serve stubs until the real services land (default `true`)               |
| `DEMO_CACHE`                                                  | A, D     | Saved answers for the scripted demo (not wired yet)                     |
| `STORE_MESSAGES`                                              | A        | Turn off to store no question or answer text (metrics are still stored) |
| `CHAT_RATE_LIMIT`, `SPEECH_RATE_LIMIT`, `FEEDBACK_RATE_LIMIT` | A        | Per-client limits, e.g. `20/m`                                          |
| `LLM_PROVIDER`, `LLM_MODEL`, `BHASHINI_*`                     | C        | Model and speech access                                                 |
| `EMBEDDING_MODEL`, `TOP_K`, `SCORE_THRESHOLD`, `QDRANT_URL`   | B        | Retrieval behaviour                                                     |
| `DATABASE_URL`                                                | A        | PostgreSQL in Compose; SQLite when unset                                |
| `NINJA_NUM_PROXIES`                                           | A        | Set to `1` behind Caddy                                                 |

## Quality checks

```bash
python -m pytest            # 49 tests: every endpoint, error path, storage and privacy rule
python -m ruff check .
python -m ruff format --check .
```

## Not done yet (Member A plan)

- **Ask page:** `DEMO_CACHE` (saved answers for the five scripted conversations when a
  service is down) and Qdrant reachability in `/health`. Real answers, retrieval and
  speech come from members B and C through the interfaces above.
- **Platform:** Docker Compose with PostgreSQL, Qdrant and Caddy; CI with the
  `openapi.json` drift check.
- **Other pages:** knowledge (Document, Chunk), `/documents`, `/schemes`, `/lessons`,
  `/grievance/guide`, `/meta/*`, and staff-only `/eval/latest`.
