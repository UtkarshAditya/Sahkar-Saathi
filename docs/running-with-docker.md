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
| `USE_STUB_SPEECH=false`                | Real speech-to-text with Whisper (see section 10)                 |
| `BHASHINI_API_KEY`, `BHASHINI_USER_ID` | Speech keys (member C)                                            |
| `LOAD_SAMPLE_DOCUMENTS=false`          | Start the library empty instead of with 9 sample entries          |

Apply changes with `docker compose up --build -d --wait`.

For a public HTTPS deployment (a real domain), see "Deploying publicly" in the root
`README.md`.

## 9. Turning on the real answer service

By default every service is a stub. Each one has its own switch, so you can turn on the
real answer service (an LLM writing answers from the retrieved passages) and leave the
rest as stubs:

| Flag                 | `true` (stub)                | `false` (real)                                       |
| -------------------- | ---------------------------- | ---------------------------------------------------- |
| `USE_STUB_ANSWER`    | Canned demonstration answers | The LLM writes a cited answer, or declines           |
| `USE_STUB_RETRIEVER` | Three sample passages        | Not built yet: every question returns an error (503) |
| `USE_STUB_SPEECH`    | A fixed transcript           | Whisper speech-to-text (section 10)                  |
| `USE_STUB_GRIEVANCE` | Template grievance guide     | Not built yet: the grievance page returns an error   |

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

**Retrieval is still a stub**, so answers cite the three sample passages, not the real
documents. When the real retriever is ready, `USE_STUB_RETRIEVER=false` is the only change.

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

## 12. Troubleshooting

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
