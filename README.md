# Sahkar Saathi

Multilingual Cooperative Governance & Legal Assistance Chatbot. SIH 2026, problem statement
**26088** (Ministry of Cooperation, NCCT).

This repository currently holds the **React front-end scaffold** and an empty **backend
folder structure**. Every page works with local mock data. There is no backend, AI,
speech or real API call yet. All sample content is labelled as sample or placeholder in
the UI, and no premium amounts, deadlines, helpline numbers or document URLs are invented.

## Quick start

Requires Node.js 20 or newer (tested on 20.18) and npm.

```bash
npm install
npm run dev        # http://localhost:5173
```

| Command | What it does |
|---|---|
| `npm run dev` | Start the Vite dev server with hot reload |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint (flat config, TypeScript, React hooks) |
| `npm run format` / `format:check` | Prettier write / check |
| `npm run typecheck` | TypeScript only |

Optional: copy `.env.example` to `.env.local` to change settings (see below).

## Stack

React 19 + TypeScript, Vite 6, Tailwind CSS 4 (via PostCSS), React Router 7, react-i18next,
Lucide icons, ESLint 9 + Prettier 3. Vite 6 is used rather than 7 because Vite 7 needs
Node 20.19+.

## Pages

| Route | Page | Priority (architecture doc) |
|---|---|---|
| `/` | Ask Sahkar Saathi: chat, citations panel, state prompt, declined state, feedback | Must |
| `/grievance` | Grievance helper: category, forum, steps, checklist, editable draft, copy and download | Must |
| `/about` | About and help: how it works, limits, privacy, sources, feedback form | Must |
| `/crop-insurance` | Crop insurance guide (PMFBY) with season and crop selectors | Should |
| `/schemes` | Schemes and services: search, category filter, details dialog | Should |
| `/library` | Law and by-laws library: search, state, language and type filters | Could |
| `/learn` | Financial literacy lessons and a three-question quiz | Could |
| `/staff/quality` | Quality dashboard (sample metrics, no auth yet) | Could |
| `/admin` | Placeholder. The real admin is Django admin | Free |

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
backend/          Directory scaffold only, see backend/README.md
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
  fall back to English. The starter file is Marathi and needs review by a native speaker.
- The chosen language and state are saved in `localStorage` (preferences only, nothing personal).

To add a string: add the key to `en.json`, then `hi.json` and `regional.json`, and use
`const { t } = useTranslation(); t('section.key')`.

## Connecting the backend

1. When the backend freezes `openapi.json`, run
   `npx openapi-typescript openapi.json -o src/types/api.ts` and re-export those types
   from `src/types/index.ts` in place of the hand-written ones.
2. Set `VITE_USE_MOCKS=false`. `src/services/api.ts` then calls `VITE_API_BASE_URL`
   (default `/api/v1`) instead of returning mock data. Pages do not change.
3. For local development, uncomment the `/api` proxy in `vite.config.ts`. In deployment
   Caddy serves `dist/` and proxies `/api` (and `/admin`) to Django on the same origin.
4. Consider TanStack Query in place of `useAsync` once real endpoints exist.

Testing hook: in mock mode, sending `/error` on the Ask page shows the error state.

## Not implemented yet (by design)

| Item | Current state | Planned |
|---|---|---|
| Voice input (mic) | Button shows a "not connected yet" notice | Sprint 2: `useRecorder` hook, `/speech/transcribe`, editable transcript |
| Listen (text to speech) | Disabled, labelled "coming soon" | Sprint 2: `/speech/synthesize` |
| Grievance voice description | Hint text only | Sprint 3 |
| Answers, schemes, documents, lessons, metrics | Local mock data with sample labels | Real endpoints |
| Feedback | Shown on screen only, not stored | `POST /feedback` |
| Staff auth for `/staff/quality` | None | Staff token (member A) |
| Admin page | Placeholder cards, no links | Django admin at `/admin/` |
| Body content translation | English only | Language service |

## Team ownership

Utkarsh: backend and platform. Zainab: knowledge and retrieval. C: agent, language and safety.
D: React front end (this scaffold) and pitch. See `backend/README.md` for backend folders.
