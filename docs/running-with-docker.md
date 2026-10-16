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
| `USE_STUBS=false`                      | Use the real services once members B and C have plugged them in   |
| `BHASHINI_API_KEY`, `BHASHINI_USER_ID` | Speech keys (member C)                                            |
| `LOAD_SAMPLE_DOCUMENTS=false`          | Start the library empty instead of with 9 sample entries          |

Apply changes with `docker compose up --build -d --wait`.

For a public HTTPS deployment (a real domain), see "Deploying publicly" in the root
`README.md`.

## 9. Troubleshooting

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
