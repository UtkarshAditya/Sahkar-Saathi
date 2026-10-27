# Sahkar Saathi

Multilingual Cooperative Governance & Legal Assistance Chatbot. SIH 2026, problem statement
**26088** (Ministry of Cooperation, NCCT).

This repository holds the **React front end** and a **Django + Ninja backend** that serves
the whole API contract (`backend/openapi.json`). By default answers, retrieval and speech
come from stub services. The real pipeline (retrieval over the ingested documents, answers
from an LLM, Whisper speech-to-text) can be switched on one service at a time; see
[What is real and what is stubbed](#what-is-real-and-what-is-stubbed). All sample content is
labelled as sample or placeholder in the UI, and no premium amounts, deadlines, helpline
numbers or document URLs are invented.

## Run everything with Docker (one command)

Requires Docker with Compose v2 (Docker Desktop on Windows and macOS). New to Docker? See
the step-by-step guide: [docs/running-with-docker.md](docs/running-with-docker.md).

```bash
docker compose up --build
```

Open **http://localhost**. The first build takes a few minutes. You get:

| Service   | What it runs                                                             | Reachable from your machine |
| --------- | ------------------------------------------------------------------------ | --------------------------- |
| `caddy`   | The React build, plus `/api`, `/admin` and `/static` proxied to Django   | ports 80 and 443            |
| `web`     | Django + Ninja under uvicorn (2 workers)                                 | no                          |
| `db`      | PostgreSQL 17                                                            | no                          |
| `qdrant`  | Qdrant vector database (unauthenticated, so never published)             | no                          |
| `secrets` | One-shot: generates the database password, Django key and admin password | no                          |

- **Admin:** http://localhost/admin/ as `admin`. The password is generated on first start:
  `docker compose exec web cat /secrets/admin_password`. In Windows Git Bash, prefix the
  command with `MSYS_NO_PATHCONV=1`.
- **Check it works:** `python scripts/smoke_test.py` runs 26 checks against the running
  stack: API, admin, security headers, and that internal ports are closed.
- **Settings:** copy `.env.example` to `.env` and change what you need; nothing is required.
- **Data** lives in Docker volumes and survives `docker compose down`. To start from
  scratch, including new secrets: `docker compose down --volumes`.
- **Logs:** `docker compose logs -f web`.

### Deploying publicly (HTTPS)

Point a DNS name at the server, open ports 80 and 443, and create a `.env` with:

```bash
SITE_ADDRESS=demo.example.org
SITE_HOST=demo.example.org
DJANGO_HTTPS=true
```

Then run `docker compose up --build -d`. Caddy obtains and renews the certificate
automatically. Django then enables HSTS, secure cookies and HTTPS redirects, and passes its
own `check --deploy` checklist with no warnings. HTTPS also makes the microphone work on
phones, which browsers allow only on HTTPS or localhost.

**What is hardened:**

- **Containers:** only Caddy is reachable from outside. Django runs as an unprivileged user
  on a read-only filesystem; every container has `no-new-privileges`, and Linux
  capabilities are dropped.
- **Secrets:** they are random, generated once and never committed. Production refuses to
  start without them, and DEBUG is forced off.
- **Headers:** a strict Content-Security-Policy and other security headers.
- **Limits:** request bodies are capped, and per-client rate limits are shared across workers.
- **Logging:** errors are logged without any message text.

## Front-end development

Requires Node.js 20 or newer (tested on 20.18) and npm. The app calls the real backend by
default, so start it first (see [backend/README.md](backend/README.md)), or set
`VITE_USE_MOCKS=true` to work on the UI with local mock data and no backend.

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api, /admin and /static to :8000)
```

| Command                           | What it does                                  |
| --------------------------------- | --------------------------------------------- |
| `npm run dev`                     | Start the Vite dev server with hot reload     |
| `npm run build`                   | Type-check (`tsc -b`) and build to `dist/`    |
| `npm run preview`                 | Serve the production build locally            |
| `npm run lint`                    | ESLint (flat config, TypeScript, React hooks) |
| `npm run format` / `format:check` | Prettier write / check                        |
| `npm run typecheck`               | TypeScript only                               |

Optional: copy `.env.example` to `.env.local` to change settings (see below).

## Stack

React 19 + TypeScript, Vite 6, Tailwind CSS 4 (via PostCSS), React Router 7, react-i18next,
Lucide icons, ESLint 9 + Prettier 3. Vite 6 is used rather than 7 because Vite 7 needs
Node 20.19+.

## Pages

| Route             | Page                                                                                   | Priority (architecture doc) |
| ----------------- | -------------------------------------------------------------------------------------- | --------------------------- |
| `/`               | Ask Sahkar Saathi: chat, citations panel, state prompt, declined state, feedback       | Must                        |
| `/grievance`      | Grievance helper: category, forum, steps, checklist, editable draft, copy and download | Must                        |
| `/about`          | About and help: how it works, limits, privacy, sources, feedback form                  | Must                        |
| `/crop-insurance` | Crop insurance guide (PMFBY) with season and crop selectors                            | Should                      |
| `/schemes`        | Schemes and services: search, category filter, details dialog                          | Should                      |
| `/library`        | Law and by-laws library: search, state, language and type filters                      | Could                       |
| `/learn`          | Financial literacy lessons and a three-question quiz                                   | Could                       |
| `/staff/quality`  | Quality dashboard (sample metrics, no auth yet)                                        | Could                       |
| `/admin`          | Placeholder. The real admin is Django admin                                            | Free                        |

"Ask about this" on the schemes, library and crop pages opens `/` with the question prefilled
(`/?q=…`). The library also passes `&doc=<id>` to limit the next question to that document.

## Folder guide

```text
src/
├── app/          App shell: App.tsx, router.tsx, providers.tsx (i18n + shared settings),
│                 navigation.ts (single source for sidebar, mobile menu and bottom bar)
├── components/
│   ├── layout/   AppLayout, Sidebar, Header, MobileNavigation, Brand
│   ├── common/   Button, Card, Badge, Notice/LegalNotice, PageHeader, EmptyState
│   │             (+ Loading/Error states), LanguageSelector, StateSelector, SearchInput,
│   │             SourceMeta, Modal
│   ├── chat/     ChatInput, MessageBubble, CitationPanel, SuggestedQuestions
│   └── feedback/ FeedbackButtons
├── pages/        One file per route
├── hooks/        useSettings, useAsync, useCopyToClipboard, useDocumentTitle
├── services/     api.ts: one function per endpoint in the API contract
├── types/        Shared types, field names match the API contract (snake_case)
├── data/         All mock and sample content (never inline sample data in pages)
├── i18n/         i18next setup and locales/{en,hi,regional}.json
├── lib/          Small helpers (date and percent formatting, text download, cn)
└── styles/       Tailwind entry and design tokens
backend/          Django + Ninja API (chat and speech endpoints), see backend/README.md
```

## Design system

Tokens live in `src/styles/index.css` under `@theme`: `brand-*` (deep green, primary),
`saffron-*` (accent, used for demo, warning and legal notices), and `canvas`, `surface`,
`line`, `ink`, `ink-soft`, `ink-muted`. The root font size is 17px for readability, so
Tailwind breakpoints (in rem) are slightly wider than default. Interactive targets are at
least 44px tall, and focus rings are visible everywhere.

## Languages

- English (`en.json`) and Hindi (`hi.json`) cover the whole shared interface: navigation,
  sidebar, header, notices, page titles and the chat UI. Page body content is English for now.
- The third language is **configurable**. Set `VITE_REGIONAL_LANGUAGE_CODE` and
  `VITE_REGIONAL_LANGUAGE_LABEL`, then put its strings in `regional.json`. Missing keys
  fall back to English. The starter file is Tamil and needs review by a native speaker.
- The chosen language and state are saved in `localStorage` (preferences only, nothing personal).

To add a string: add the key to `en.json`, then `hi.json` and `regional.json`, and use
`const { t } = useTranslation(); t('section.key')`.

## Connecting the backend

The Django backend in `backend/` serves every endpoint the pages use; the full list is in
[backend/README.md](backend/README.md). To use it:

1. Start the backend: `uvicorn config.asgi:application --reload --port 8000`.
2. Run the front end with `npm run dev`. Vite proxies `/api`, `/admin` and `/static` to
   port 8000, exactly as Caddy does in Docker, so no CORS setup is needed.
3. For the Quality dashboard, log in as a staff user at `/admin/` first, on the same
   origin (the Vite or Caddy address).

**The contract is frozen** in `backend/openapi.json`:

- `npm run gen:api` regenerates `src/types/api.gen.ts` from it. Never edit that file.
- `src/types/contract-check.ts` checks at compile time that the hand-written types in
  `src/types/index.ts` fit the contract, so `npm run build` fails if they drift.
- After a contract change: re-export `openapi.json` in the backend, run `npm run gen:api`,
  then fix anything `npm run build` reports. CI runs the same checks on every pull request.

Consider TanStack Query in place of `useAsync` now that real endpoints exist.

Testing hook: in mock mode, sending `/error` on the Ask page shows the error state.

## What is real and what is stubbed

Every service defaults to a stub, so the app, CI and `scripts/smoke_test.py` run with no
network, no model download and no LLM. Each real service has its own switch
(`USE_STUB_RETRIEVER`, `USE_STUB_ANSWER`, `USE_STUB_SPEECH`, `USE_STUB_GRIEVANCE`).

| Part                         | Default                      | When switched on                                                               |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------ |
| Retrieval                    | Three canned sample passages | Qdrant search with multilingual-e5 embeddings, after `manage.py ingest_corpus` |
| Answers                      | Canned demonstration answers | The LLM writes a cited answer from the retrieved passages, or declines         |
| Speech to text               | A fixed transcript           | Whisper (faster-whisper)                                                       |
| Text to speech (Listen)      | Silent WAV audio             | Still a stub, also with `USE_STUB_SPEECH=false`                                |
| Grievance guide              | Keyword categories, template | Not built yet: the real flag returns `503`                                     |
| Bhashini speech and language | Not used                     | Not built yet                                                                  |

The LLM is any OpenAI-compatible server (Ollama on your machine, or a hosted API). Whether
the answers are good is measured, not assumed: `manage.py eval_retrieval` and
`scripts/acceptance.py` (see `data/eval/README.md`). The steps are in
[docs/running-with-docker.md](docs/running-with-docker.md), sections 9 to 12.

## Not implemented yet

| Item                        | Current state                                                                            | Planned                                                                 |
| --------------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Verified corpus in use      | Stub retrieval unless the corpus is ingested                                             | Ingest the verified PDFs, set `SCORE_THRESHOLD` from `eval_retrieval`   |
| Voice input (mic)           | Button shows a "not connected yet" notice                                                | Sprint 2: `useRecorder` hook, `/speech/transcribe`, editable transcript |
| Listen (text to speech)     | Disabled, labelled "coming soon"                                                         | Sprint 2: `/speech/synthesize` (endpoint and client already exist)      |
| Grievance voice description | Hint text only                                                                           | Sprint 3                                                                |
| Quality dashboard data      | Sample numbers from `/eval/latest` (staff only)                                          | Sprint 2: EvalRun models filled by member B's eval runner               |
| Library documents           | The `sources.csv` rows that pass validation; the 9 samples load only into an empty table | Fix the rows `load_sources` reports as skipped, then ingest             |
| Body content translation    | English only                                                                             | Language service                                                        |

## Team ownership

Utkarsh: backend and platform. Zainab: knowledge and retrieval. C: agent, language and safety.
D: React front end (this scaffold) and pitch. See `backend/README.md` for backend folders.
