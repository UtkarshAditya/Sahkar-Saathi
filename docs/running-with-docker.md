# Running Sahkar Saathi locally with Docker

This guide runs the whole project on your machine: the React app, the Django API,
PostgreSQL, Qdrant and the Caddy web server. You do not need Python or Node.js installed;
Docker builds everything.

## 1. Install Docker (once)

| Your OS | Install                                                                                                        |
| ------- | -------------------------------------------------------------------------------------------------------------- |
| Windows | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (uses WSL 2; accept the prompt to enable it) |
| macOS   | [Docker Desktop](https://www.docker.com/products/docker-desktop/)                                              |
| Linux   | [Docker Engine](https://docs.docker.com/engine/install/) and the Compose plugin                                |

Give Docker at least **4 GB of memory** (Docker Desktop → Settings → Resources).

Check that it works. Docker Desktop must be **running**, with its whale icon in the
taskbar or menu bar:

```bash
docker --version
docker compose version
docker info          # fails with "cannot connect" if the engine is not running
```

## 2. Get the code

```bash
git clone https://github.com/UtkarshAditya/Sahkar-Saathi.git
cd Sahkar-Saathi
```

Already cloned? Update it instead: `git pull`.

## 3. Start everything

From the repository root (the folder with `docker-compose.yml`):

```bash
docker compose up --build
```

The first run downloads images and builds the app, which takes about 3 to 5 minutes. The
stack is ready when the log shows `Application startup complete` and the `caddy`
container is running. Leave this terminal open; press `Ctrl+C` to stop.

Prefer to get your terminal back? Run it in the background and wait until every service is
healthy:

```bash
docker compose up --build -d --wait
```

## 4. Open the app

| What       | URL                                                           |
| ---------- | ------------------------------------------------------------- |
| The app    | http://localhost                                              |
| Admin site | http://localhost/admin/                                       |
| API docs   | http://localhost/api/v1/docs (log in to the admin site first) |
| Health     | http://localhost/api/v1/health                                |

Answers come from **stub** services (marked "Demonstration answer") until the real
retrieval and answer services are connected.

## 5. Log in to the admin site

The user name is `admin`. The password is generated on the first start and stored inside
the stack. Show it with the command for your terminal:

```powershell
# Windows PowerShell or Command Prompt
docker compose exec web cat /secrets/admin_password
```

```bash
# macOS, Linux
docker compose exec web cat /secrets/admin_password

# Windows Git Bash: stop Git Bash from rewriting the path
MSYS_NO_PATHCONV=1 docker compose exec web cat /secrets/admin_password
```

Each machine gets its own password. You can change it in the admin site (top right,
"Change password"); restarts never reset it.

Logging in to the admin site also unlocks the **Quality dashboard** at
http://localhost/staff/quality.

## 6. Check that everything works

The smoke test runs 26 checks against the running stack (needs Python 3.10+):

```bash
python scripts/smoke_test.py
```

It ends with `All checks passed.` if the app, API, admin site, security headers and
network isolation are all as expected.

## 7. Everyday commands

Run all of these from the repository root.

| Task                              | Command                                              |
| --------------------------------- | ---------------------------------------------------- |
| Start (build only what changed)   | `docker compose up --build -d --wait`                |
| See which services are running    | `docker compose ps`                                  |
| Follow the API logs               | `docker compose logs -f web`                         |
| Logs of every service             | `docker compose logs -f`                             |
| Stop (keeps your data)            | `docker compose down`                                |
| Restart just the API              | `docker compose restart web`                         |
| Rebuild after `git pull`          | `docker compose up --build -d --wait`                |
| Open a shell in the API container | `docker compose exec web sh`                         |
| Run a Django command              | `docker compose exec web python manage.py <command>` |
| Open a database shell             | `docker compose exec db psql -U sahkar sahkar`       |

**Your data is kept** in Docker volumes when you stop or rebuild: chats, feedback,
documents, the admin account and the generated secrets.

**Start completely fresh.** This deletes all data and generates new secrets, including a
new admin password:

```bash
docker compose down --volumes
docker compose up --build
```

## 8. Settings (optional)

Nothing needs configuring to run locally. To change something, copy the example file
and edit it:

```bash
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Common changes:

| Setting                                | Why                                                               |
| -------------------------------------- | ----------------------------------------------------------------- |
| `HTTP_PORT=8080`                       | Port 80 is taken on your machine. Then open http://localhost:8080 |
| `USE_STUB_ANSWER=false`                | Real answers from an LLM (see section 9)                          |
| `USE_STUB_RETRIEVER=false`             | Real retrieval over the ingested documents (see section 12)       |
| `USE_STUB_SPEECH=false`                | Real speech-to-text with Whisper (see section 10)                 |
| `INSTALL_ML=false`                     | A smaller, stub-only image: no PyTorch, so no real retrieval      |
| `SCORE_THRESHOLD`                      | Default 0.82, provisional; re-tune with `eval_retrieval` (§ 12)   |
| `BHASHINI_API_KEY`, `BHASHINI_USER_ID` | Speech keys (member C)                                            |
| `LOAD_SAMPLE_DOCUMENTS=false`          | Start the library empty instead of with 9 sample entries          |

Apply changes with `docker compose up --build -d --wait`.

For a public HTTPS deployment (a real domain), see "Deploying publicly" in the root
`README.md`.

## 9. Turning on the real answer service

By default every service is a stub. Each one has its own switch, so you can turn on the
real answer service (an LLM writing answers from the retrieved passages) and leave the
rest as stubs:

| Flag                 | `true` (stub)                | `false` (real)                                                                                                      |
| -------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `USE_STUB_ANSWER`    | Canned demonstration answers | The LLM writes a cited answer, or declines                                                                          |
| `USE_STUB_RETRIEVER` | Three sample passages        | Qdrant search over the ingested corpus (section 12)                                                                 |
| `USE_STUB_SPEECH`    | A fixed transcript           | Whisper speech-to-text (section 10)                                                                                 |
| `USE_STUB_GRIEVANCE` | Template grievance guide     | Forums and contacts from `forums.yaml` (crop insurance only so far; other categories say the route is not recorded) |

An empty flag follows `USE_STUBS` (default `true`). The LLM can be any server with an
OpenAI-compatible API.

**Example 1: Ollama on your own machine.** Install [Ollama](https://ollama.com), then
download a model:

```bash
ollama pull llama3.1:8b
```

Put this in `.env`:

```bash
USE_STUB_ANSWER=false
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=llama3.1:8b
LLM_API_KEY=ollama
```

`host.docker.internal` is how the container reaches your machine. On Linux, also make
Ollama listen on all interfaces: `OLLAMA_HOST=0.0.0.0 ollama serve`.

**Example 2: a hosted OpenAI-compatible API.** Use the URL, key and model name from your
provider. The values below are placeholders:

```bash
USE_STUB_ANSWER=false
LLM_BASE_URL=https://api.example-provider.com/v1
LLM_MODEL=example-model-name
LLM_API_KEY=your-api-key-here
# Only if the provider rejects JSON mode:
# LLM_JSON_MODE=false
```

Never commit `.env`: it holds your key.

Then apply it and ask a question:

```bash
docker compose up --build -d --wait
docker compose logs -f web      # each question logs its status and latency
```

**Until you turn on the real retriever, retrieval is still a stub**, so answers cite the
three sample passages, not the real documents. To search the real documents, ingest them
and set `USE_STUB_RETRIEVER=false`: section 12.

If the LLM cannot be reached, the app shows an error ("An upstream service failed") and
the log shows `provider error: LLM call failed ...` with the model and URL it tried.

## 10. Real speech-to-text

```bash
# .env
USE_STUB_SPEECH=false
WHISPER_MODEL=small        # tiny or base are faster and less accurate
```

Then `docker compose up --build -d --wait`.

- The first start downloads the Whisper model (about 500 MB for `small`) into the `models`
  volume, so it is slow; later starts reuse it. Start-up waits at most `WARM_TIMEOUT`
  seconds (default 300) for the download, then serves anyway and loads the model on the
  first recording.
- Check progress with `docker compose logs web`. Look for
  `warm_models: Whisper model 'small' loaded in ... s`, or a warning saying why it could
  not load.
- Listen (text-to-speech) still plays the stub's silent audio.
- `docker compose down --volumes` deletes the downloaded model too.

## 11. Updating the document list

The library's document list comes from `data/sources.csv`, which is mounted read-only
into the API container and loaded on every start. After editing it, check it first:

```bash
docker compose exec web python manage.py load_sources --dry-run
```

This prints how many rows would be created, updated or skipped, and why each skipped row
was rejected. Nothing is written. Then load it:

```bash
docker compose exec web python manage.py load_sources
```

Rows that are invalid are skipped, never guessed or fixed. Documents not in the CSV
(samples, or ones added in the admin site) are left alone.

## 12. Loading the real corpus

The real pipeline answers from documents that have been read into PostgreSQL (the text
chunks) and Qdrant (their vectors). Do these steps in order:

1. **Put the PDFs in `data/raw/`**, taken from the team Drive. The folder is mounted
   read-only into the API container. The file names must match the `local_path` column of
   `data/sources.csv`. Optionally fetch the ones with direct links first:

   ```bash
   python scripts/download_pdfs.py     # certificates are verified; --insecure is a last resort
   ```

   > **PDFs and git.** Some PDFs are already tracked in the repository (they were added
   > with `git add -f`). The pattern `data/raw/*` is still in `.gitignore`, so a new PDF is
   > ignored unless it is added with `git add -f data/raw/<file>.pdf`. A PDF that is only on
   > your machine is not shared with the team until someone does that or puts it on the Drive.

2. **Start the stack.** The first build installs PyTorch and the other ML packages, which
   takes several minutes and makes the image much larger (`INSTALL_ML=false` in `.env`
   skips them). On start, `load_sources` loads the document list into the database.

   ```bash
   docker compose up --build -d --wait
   ```

3. **Ingest the documents.** This reads every `use_in_corpus=Y` row of the CSV, cuts the
   PDF into chunks, embeds them and writes them to PostgreSQL and Qdrant. The first run
   also downloads the embedding model into the `models` volume. It is safe to run again:
   each document's chunks are replaced. It ends with a summary and lists every document
   that needs attention (PDF missing, no text, or no document row).

   ```bash
   docker compose exec web python manage.py ingest_corpus
   ```

4. **Check what was ingested.** Every document should have chunks, and PostgreSQL and
   Qdrant should agree on the count:

   ```bash
   docker compose exec web python manage.py corpus_status
   ```

5. **Switch the pipeline on.** In `.env`, set the flags and the LLM (section 9), then
   recreate the API container:

   ```bash
   USE_STUB_RETRIEVER=false
   USE_STUB_ANSWER=false
   LLM_BASE_URL=http://host.docker.internal:11434/v1
   LLM_MODEL=llama3.1:8b
   ```

   ```bash
   docker compose up -d
   ```

6. **Measure retrieval and set the threshold.** `eval_retrieval` runs the questions in
   `data/eval/retrieval_questions.json`, prints the hit rate and suggests a
   `SCORE_THRESHOLD`. Put the suggestion in `.env` (do not guess it), apply it, and run the
   acceptance conversations in `data/eval/conversations.json`:

   ```bash
   docker compose exec web python manage.py eval_retrieval
   # edit .env: SCORE_THRESHOLD=<the suggested value>, and DEMO_CACHE=false
   docker compose up -d
   python scripts/acceptance.py
   ```

   `acceptance.py` tells live answers from demo answers. With `DEMO_CACHE=true`, or with
   any stub still on, the answers are `is_demo=true`: the lines read `DEMO` and the run
   fails, because a pass on saved answers says nothing about the live pipeline. Check the
   live pipeline with `DEMO_CACHE=false`; `--allow-demo` is only for rehearsing the demo.

   To show a run on the Quality dashboard, add `--record` once the real retriever is on
   (it refuses to record the stub's scores). The dashboard needs all three metrics: the
   command measures the hit rate and the correct-refusal rate, and faithfulness is a
   number you enter after checking answers by hand, either with `--faithfulness 0.85` or
   in the admin site under Eval runs. Until then the dashboard keeps showing its previous
   run, or the sample data.

   Read `data/eval/README.md` for both file formats. The suggestion is only as good as the
   question set: it warns when the in-scope and out-of-scope scores overlap or when a group
   has fewer than 5 questions.

**If something goes wrong:**

| Problem                                            | Likely cause and fix                                                                                                                                                           |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `/chat/ask` returns 503 `service_not_ready`        | The retriever is unavailable: the image was built with `INSTALL_ML=false` (rebuild with `INSTALL_ML=true`), or a package is missing. `docker compose logs web` names it.       |
| `/chat/ask` returns 500 with the real retriever on | Usually Qdrant has no collection yet (run `ingest_corpus`) or is down (`docker compose ps`). The error is in `docker compose logs web`.                                        |
| `/chat/ask` returns 502 `provider_error`           | The LLM cannot be reached. Check it is running, that `LLM_BASE_URL` is right (`host.docker.internal` for Ollama on your machine) and the key. The log names the URL and model. |
| Every question is declined                         | `SCORE_THRESHOLD` is too high for the embedding scores, or nothing is ingested. Run `corpus_status`, then `eval_retrieval` and use its suggested value.                        |
| The first question or the first start is slow      | The models download into the `models` volume the first time (`docker compose logs web`). Later starts reuse them.                                                              |
| `ingest_corpus` lists "no Document row"            | `load_sources` skipped that row of the CSV as invalid. `load_sources --dry-run` shows why; the CSV owner fixes the row.                                                        |
| `ingest_corpus` lists "PDF not found"              | The file in `data/raw/` is missing or named differently from `local_path` in `data/sources.csv`.                                                                               |
| `ingest_corpus` says it needs the ML packages      | The image was built with `INSTALL_ML=false`. Rebuild with `INSTALL_ML=true`.                                                                                                   |

## 13. Troubleshooting

| Problem                                                                      | Fix                                                                                                                   |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `cannot connect to the Docker daemon` / `dockerDesktopLinuxEngine` not found | Start Docker Desktop and wait until it says "Engine running".                                                         |
| `port is already allocated` or `bind: address already in use` on 80 or 443   | Another program (IIS, Skype, another web server) uses the port. Set `HTTP_PORT=8080` and `HTTPS_PORT=8443` in `.env`. |
| A container stays `unhealthy` or keeps restarting                            | `docker compose logs web` (or `db`, `caddy`) shows why.                                                               |
| The page loads but answers fail                                              | `docker compose logs -f web`, then ask again; the error is logged with a traceback.                                   |
| `cat: 'C:/Program Files/Git/secrets/...': No such file`                      | You are in Git Bash: prefix the command with `MSYS_NO_PATHCONV=1` (step 5).                                           |
| Admin login says the password is wrong                                       | Copy the whole output of the step 5 command. After `docker compose down --volumes` the password changes.              |
| Changes you pulled do not show up                                            | Rebuild: `docker compose up --build -d --wait`, then hard-refresh the browser (`Ctrl+Shift+R`).                       |
| Build fails with "no space left on device"                                   | `docker system prune` removes unused images and build cache.                                                          |
| Microphone does not work on a phone                                          | Browsers only allow it on HTTPS or `localhost`. Use a public HTTPS deployment for phone tests.                        |

## 14. Before the demo

**Settings.** For a laptop or a public host, put these in `.env` (a public host also needs
the three HTTPS lines from "Deploying publicly" in the root `README.md`):

```bash
DEMO_CACHE=true          # the scripted demo questions get their saved answers, and keep
                         # working if the LLM or the vector store is down
# USE_STUB_* and LLM_*   # as in sections 9 to 12, if the real pipeline is on
```

`DEMO_CACHE` only touches the questions in `data/eval/conversations.json`. Any other
question goes through the normal service, and a failure there is still an error. The saved
answers are in `backend/data/demo_answers.yaml`; two of them are labelled placeholders
until the owners supply sourced text.

**Run the demo check** after `docker compose up -d --wait`. It visits every screen's
endpoint in demo order, plays the five scripted conversations, and prints a PASS or FAIL
table (exit code 1 if anything fails):

```bash
python scripts/demo_smoke.py                         # http://localhost
python scripts/demo_smoke.py https://demo.example.org
```

`/eval/latest` is staff only. Without a login the check confirms that anonymous access is
refused. To check the data too, pass a staff login through the environment, so the password
never appears in the command line:

```bash
# Windows PowerShell
$env:DEMO_STAFF_USER = "admin"
$env:DEMO_STAFF_PASSWORD = docker compose exec -T web cat /secrets/admin_password
python scripts/demo_smoke.py

# macOS, Linux, Git Bash
DEMO_STAFF_USER=admin \
DEMO_STAFF_PASSWORD="$(MSYS_NO_PATHCONV=1 docker compose exec -T web cat /secrets/admin_password)" \
python scripts/demo_smoke.py
```

Against an `https://` address it also checks the HSTS header and the Secure cookie flag.
Use `--api-only` to skip the front-end check when only the backend is running. For a quick
check that the stack itself is locked down, `python scripts/smoke_test.py` is the other
script.

**On the day:** keep ports 80 and 443 for a public host (the certificate needs them), do
not run `docker compose down --volumes` on it (that discards the certificate and the
admin password), and run the demo check from a second device on the same network.

## 15. Known limits of the live run

What the first end-to-end run with Ollama and `llama3.1:8b` showed (details in
`data/eval/last_live_run.md`). Treat the live pipeline as a rehearsal, not a finished system.

- **Tamil is weak and slow.** The Tamil answers took 79 to 88 s, against 5 to 25 s for
  English, and the Tamil PMFBY answer repeated the question back instead of answering. The
  acceptance test now fails an answer that is not in Tamil script or that repeats the
  question (`answer_script` in `data/eval/README.md`). A fluent speaker must read the Hindi
  and Tamil answers.
- **The score threshold is provisional.** `SCORE_THRESHOLD` defaults to 0.82. It comes from
  six PMFBY-only evaluation questions: off-topic questions scored up to 0.813 and the lowest
  answerable one 0.8298. Scores are lower in Hindi and Tamil than in English, and no
  threshold can stop an on-topic question that the corpus does not cover. Re-tune it with
  `eval_retrieval` once real in-scope questions with expected documents are added.
- **About half of the corpus is ingested.** 13 of the 26 documents marked `use_in_corpus=Y`
  have a file; the rest could not be downloaded (see section 12). The PMFBY documents are
  among the missing ones, so the "72 hours" question is correctly declined and the first
  PMFBY acceptance turns fail until those PDFs are added and ingested.
- **An answer can misapply a passage it cites.** The prompt now forbids using a passage about
  a different procedure or kind of case, but nothing checks it automatically. Read the
  cited passage next to every answer you show.
- **Low host memory makes Ollama very slow.** On the test machine only 0.3 GB of 15.7 GB
  was free, and 42% of the model fitted in the 4 GB graphics memory; the rest ran on the CPU.
  Close other programs, keep a single model loaded (`ollama ps`), let the first question
  after a model switch take a while, and raise `LLM_TIMEOUT` (150 s in the test) if you
  see 502 errors.

## What is running

```text
your browser ──► caddy :80/:443 ──► React app (static files)
                       │
                       ├── /api, /admin ──► web (Django + uvicorn) ──► db (PostgreSQL)
                       │                                          └──► qdrant (vectors)
                       └── /static ──► admin and API-docs assets
```

Only `caddy` is reachable from your machine. The database, Qdrant and the API itself are
on a private Docker network.
