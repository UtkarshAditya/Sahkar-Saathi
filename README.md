# Sahkar Saathi

Multilingual Cooperative Governance & Legal Assistance Chatbot. SIH 2026, problem statement
**26088** (Ministry of Cooperation, NCCT).

This repository holds the **React front end** and a **Django + Ninja backend** that
serves `/chat/ask` and the two `/speech` endpoints from stub services. By default every
page works with local mock data; set `VITE_USE_MOCKS=false` to use the backend instead.
There is no real AI, retrieval or speech provider yet. All sample content is labelled as
sample or placeholder in the UI, and no premium amounts, deadlines, helpline numbers or
document URLs are invented.

## Quick start

Requires Node.js 20 or newer (tested on 20.18) and npm.

```bash
npm install
npm run dev        # http://localhost:5173
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
2. Run the front end with `VITE_USE_MOCKS=false npm run dev`. Vite proxies `/api` to
   port 8000, so no CORS setup is needed. In deployment Caddy does the same.
3. For the Quality dashboard, log in as a staff user at `/admin/` first (on the same
   origin, so through the Vite or Caddy address).

**The contract is frozen** in `backend/openapi.json`:

- `npm run gen:api` regenerates `src/types/api.gen.ts` from it. Never edit that file.
- `src/types/contract-check.ts` checks at compile time that the hand-written types in
  `src/types/index.ts` fit the contract, so `npm run build` fails if they drift.
- After a contract change: re-export `openapi.json` in the backend, run `npm run gen:api`,
  then fix anything `npm run build` reports. CI runs the same checks on every pull request.

Consider TanStack Query in place of `useAsync` now that real endpoints exist.

Testing hook: in mock mode, sending `/error` on the Ask page shows the error state.

## Not implemented yet (by design)

| Item                                          | Current state                             | Planned                                                                 |
| --------------------------------------------- | ----------------------------------------- | ----------------------------------------------------------------------- |
| Voice input (mic)                             | Button shows a "not connected yet" notice | Sprint 2: `useRecorder` hook, `/speech/transcribe`, editable transcript |
| Listen (text to speech)                       | Disabled, labelled "coming soon"          | Sprint 2: `/speech/synthesize`                                          |
| Grievance voice description                   | Hint text only                            | Sprint 3                                                                |
| Answers, schemes, documents, lessons, metrics | Local mock data with sample labels        | Real endpoints                                                          |
| Feedback                                      | Shown on screen only, not stored          | `POST /feedback`                                                        |
| Staff auth for `/staff/quality`               | None                                      | Staff token (member A)                                                  |
| Admin page                                    | Placeholder cards, no links               | Django admin at `/admin/`                                               |
| Body content translation                      | English only                              | Language service                                                        |

## Team ownership

Utkarsh: backend and platform. Zainab: knowledge and retrieval. C: agent, language and safety.
D: React front end (this scaffold) and pitch. See `backend/README.md` for backend folders.
