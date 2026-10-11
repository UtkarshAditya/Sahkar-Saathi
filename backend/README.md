# Sahkar Saathi backend (scaffold only)

This folder is a **directory scaffold**. Nothing is implemented yet: there is no Django
project, no Python modules, no dependencies and no configuration. Each folder holds a
`.gitkeep` so Git tracks it. Delete the `.gitkeep` once the folder has real files.

The design follows `26088 Final Solution Architecture` (sections 2, 4 and 6). The API stays
thin and the AI logic lives in plain-Python code with **no Django imports**, so it can be
tested and evaluated on its own.

## Layout and owners

Owners follow the work division in the architecture document:
A = backend and platform, B = knowledge and retrieval, C = agent, language and safety.

| Folder | Responsibility | Owner |
|---|---|---|
| `config/` | Django project settings, URL root, ASGI entry point (served by uvicorn). Model names, thresholds, top-k and prompt versions are **settings**, not constants. | A |
| `apps/` | Django apps: Ninja routers (endpoints under `/api/v1/`) and database models. Keep handlers thin; call into `ai/` and `services/`. | A (models in `knowledge/` and `evaluation/`: B) |
| `apps/chat/` | `POST /chat/ask`; `Conversation`, `Message`, `Citation` models. | A |
| `apps/knowledge/` | `Document` and `Chunk` models, `GET /documents`, the `ingest` management command. | B |
| `apps/grievance/` | `POST /grievance/guide`; `GrievanceCase` (drafts are never filed). | A |
| `apps/schemes/` | `GET /schemes`, `/schemes/{slug}` from `schemes.yaml`, including `pmfby`. | A |
| `apps/lessons/` | `GET /lessons` for financial-literacy lessons and the quiz. | A |
| `apps/feedback/` | `POST /feedback`; `Feedback` model for the admin review queue. | A |
| `apps/evaluation/` | `TestQuestion`, `EvalRun`, `EvalResult`; `GET /eval/latest` (staff token); the eval runner command. | B |
| `ai/` | Plain-Python AI layer, no Django imports. | C (embeddings: B) |
| `ai/llm/` | One wrapper around the chosen language model (local or hosted), chosen by evaluation. | C |
| `ai/langchain/` | Framework glue, if LangChain is chosen as the RAG framework (or LlamaIndex: pick one). | C |
| `ai/rag/` | Grounded answer step: answer only from retrieved passages, copy numbers exactly, validate that every claim cites a passage. | C |
| `ai/agents/` | Router and the five tools (search, grievance guide, scheme lookup, helpline, ask-state). | C |
| `ai/prompts/` | Versioned prompt templates and the JSON output schema. | C |
| `ai/embeddings/` | Multilingual embedding model loading (e.g. multilingual-e5 or BGE-M3), run locally. | B |
| `ai/safety/` | Score threshold, decline path, out-of-scope handling and legal-information guardrails. | C |
| `services/` | Plain-Python services the API calls. | B, C |
| `services/retrieval/` | `VectorStore` interface over Qdrant: filters by state, language and date; top-k with scores. | B |
| `services/speech/` | Speech to text and text to speech: convert browser audio to 16 kHz mono WAV (ffmpeg), Bhashini first, Whisper fallback. | C |
| `services/translation/` | Translation between English, Hindi and the regional language (Bhashini). | C |
| `tests/` | pytest suites, including an integration test of `/chat/ask`. | All |

## Contract with the front end

The React app in the repository root already calls these endpoints through
`src/services/api.ts`, using local mock data while `VITE_USE_MOCKS=true`. The request and
response shapes it expects are in `src/types/index.ts`. When the Ninja schemas are ready,
freeze `openapi.json` and the front end will generate its types from it.

Conventions: every answer carries `status` and `citations`; a declined answer has no
citations and names a contact; errors use `{ "code": "...", "message": "..." }`; language
codes are short ISO codes (`en`, `hi`, `mr`).

## Not in this scaffold

Django initialisation, models, dependencies, database configuration, Docker Compose,
Caddy, and any AI, RAG, agent, speech or API logic. Those are Sprint 1 tasks for members
A, B and C.
