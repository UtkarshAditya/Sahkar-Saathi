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

| Method and path           | Purpose                | In                                                                  | Out                                                                                                                                                           |
| ------------------------- | ---------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST /chat/ask`          | Ask a question in text | JSON: `text`, `language`, `state`, `conversation_id`, `document_id` | `conversation_id`, `message_id`, `answer_text`, `status` (`answered`/`partial`/`declined`), `needs_state`, `citations[]`, `followups[]`, `contact`, `is_demo` |
| `POST /speech/transcribe` | Speech to text         | multipart: `audio` file, `language_hint`                            | `text`, `language`, `confidence`, `is_demo`                                                                                                                   |
| `POST /speech/synthesize` | Text to speech         | JSON: `text`, `language`                                            | `audio/wav` (16 kHz mono)                                                                                                                                     |
| `GET /health`             | Deployment check       |                                                                     | `status`, `version`, `stubs`                                                                                                                                  |

**Contract rules**

- A declined answer has no citations and always names a `contact`. The API layer enforces
  this even if a service gets it wrong.
- Every error has the shape `{"code": "...", "message": "..."}`. The codes are:
  `validation_error` (422), `unsupported_audio_type` (415), `audio_too_large` (413),
  `empty_audio` (400), `service_not_ready` (503), `provider_error` (502),
  `internal_error` (500).
- Language codes are `en`, `hi` and `REGIONAL_LANGUAGE_CODE` (default `mr`).
- Audio uploads are checked for type and size (`SPEECH_MAX_UPLOAD_BYTES`, default 5 MB)
  before they are read.
- Logs record status and latency, never question or answer text.

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
│                    errors.py (one error shape), services.py (wiring functions)
├── apps/            Django apps: thin Ninja routers and (later) models
│   ├── chat/        POST /chat/ask
│   ├── speech/      POST /speech/transcribe, /speech/synthesize
│   └── knowledge/ grievance/ schemes/ lessons/ feedback/ evaluation/   (not started)
├── services/        plain Python, no Django imports
│   ├── types.py     the interfaces: Retriever, AnswerService, SpeechProvider, + dataclasses
│   ├── stubs.py     stub implementations served while USE_STUBS=true
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
questions without a state return `needs_state`; a state other than `MH` gives `partial`;
gibberish and out-of-scope questions are declined with a contact. Transcription returns a
fixed sentence, and synthesis returns silent WAV audio.

## Settings

All settings come from environment variables; see [`.env.example`](.env.example). These
are the ones the team shares:

| Setting                                                     | Owner    | Purpose                                                    |
| ----------------------------------------------------------- | -------- | ---------------------------------------------------------- |
| `USE_STUBS`                                                 | everyone | Serve stubs until the real services land (default `true`)  |
| `DEMO_CACHE`                                                | A, D     | Saved answers for the scripted demo (not wired yet)        |
| `STORE_MESSAGES`                                            | A        | Turn off to store no message text (used once models exist) |
| `LLM_PROVIDER`, `LLM_MODEL`, `BHASHINI_*`                   | C        | Model and speech access                                    |
| `EMBEDDING_MODEL`, `TOP_K`, `SCORE_THRESHOLD`, `QDRANT_URL` | B        | Retrieval behaviour                                        |
| `DATABASE_URL`                                              | A        | PostgreSQL in Compose; SQLite when unset                   |
| `NINJA_NUM_PROXIES`                                         | A        | Set to `1` behind Caddy                                    |

## Quality checks

```bash
python -m pytest            # 21 tests covering all three endpoints and every error path
python -m ruff check .
python -m ruff format --check .
```

## Not done yet (Member A plan)

Docker Compose and the Caddyfile, PostgreSQL and Qdrant services, models (Document,
Chunk, Conversation, Message, Citation and the rest), the remaining endpoints, rate
limiting, staff authentication for `/eval/latest`, CI with the `openapi.json` drift check,
and `DEMO_CACHE`.
