# Local Development Setup — Parts 2.1–2.5

Everything runs natively. **No Docker.** Follow the section for your OS, then run the connectivity check.

| Tool | Version | Why |
|---|---|---|
| Python | **3.11.x** | FastAPI backend + AI worker |
| Node.js | **20 or 22** LTS (`.nvmrc` = 20) | Next.js 14 frontend |
| npm | ≥ 10 | Workspaces (`apps/*`, `packages/*`) |
| PostgreSQL | **15** | Primary database |
| Redis | 7.x API (Memurai on Windows) | Celery broker, cache, rate limits |

## 1. Install the tools

### Windows 10/11 (winget)

```powershell
winget install --id Python.Python.3.11 -e
winget install --id OpenJS.NodeJS.LTS -e          # skip if `node -v` already shows v20 or v22
winget install --id PostgreSQL.PostgreSQL.15 -e   # note the superuser password you set
winget install --id Memurai.MemuraiDeveloper -e   # Redis-compatible, runs as a Windows service
```

Each installer shows a UAC prompt. Click **Yes**.

- **Memurai fails with MSI error 1603** ("Failed to create temp directory")? Run the MSI directly instead: download it from memurai.com, then run `msiexec /i Memurai-Developer-v4.1.2.msi` from an elevated terminal.
- **Memurai Developer is free for development**, but it stops after **10 days of continuous uptime**. A reboot, or `Restart-Service Memurai` (elevated), resets the timer.
- **Lock PostgreSQL to localhost**, recommended on laptops. Run this as superuser, then restart the service (elevated):
  ```powershell
  psql -h localhost -U postgres -c "ALTER SYSTEM SET listen_addresses = 'localhost'"
  Restart-Service postgresql-x64-15
  ```

`psql` lives in `C:\Program Files\PostgreSQL\15\bin`. Add it to your PATH or call it by full path.

### macOS (Homebrew)

```bash
brew install python@3.11 node@20 postgresql@15 redis
brew services start postgresql@15
brew services start redis
```

Homebrew's PostgreSQL uses your macOS username as the superuser (no password). In the commands below, replace `-U postgres` with `-U "$USER"`.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv postgresql-15 redis-server
# Node 20 via NodeSource or nvm: https://github.com/nvm-sh/nvm
sudo systemctl enable --now postgresql redis-server
```

If `postgresql-15` isn't in your release, add the PGDG repo first: <https://www.postgresql.org/download/linux/ubuntu/>. Ubuntu's superuser is reached with `sudo -u postgres psql` instead of `-U postgres`.

## 2. Install project dependencies

From the repo root:

```bash
npm install                                   # frontend + design system (workspaces)

python3.11 -m venv apps/api/.venv             # Windows: py -3.11 -m venv apps/api/.venv
# activate — Windows: apps\api\.venv\Scripts\Activate.ps1   macOS/Linux: source apps/api/.venv/bin/activate
python -m pip install -r apps/api/requirements-dev.txt
```

| File | Contents |
|---|---|
| `package.json` (root) | npm workspaces, scripts, `engines: node >=20 <23` |
| `apps/web/package.json` | Next.js 14, React 18, Tailwind |
| `apps/api/requirements.txt` | FastAPI, Uvicorn, SQLAlchemy 2, Alembic, psycopg 3, Redis, Celery, pydantic-settings |
| `apps/api/requirements-dev.txt` | + pytest, ruff |

## 3. Create the database and user

Pick a strong password for the app user, then run (as the PostgreSQL superuser):

```bash
psql -h localhost -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -v app_password='YOUR-APP-PASSWORD' -f apps/api/scripts/create_db.sql
```

This creates role `vysel` and database `vysel` (UTF-8, owned by `vysel`). It is idempotent: re-running it is safe and resets the password.

## 4. Configure connection variables

```bash
cp apps/api/.env.example apps/api/.env        # Windows: Copy-Item apps/api/.env.example apps/api/.env
```

Edit `apps/api/.env` and replace `CHANGE_ME` with the app password:

```dotenv
DATABASE_URL=postgresql+psycopg://vysel:YOUR-APP-PASSWORD@localhost:5432/vysel
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/2
```

Keep Redis on `127.0.0.1`, not `localhost`. On Windows, `localhost` tries IPv6 first while Memurai listens on IPv4 only, which costs about **2 s per connection** and makes Celery time out.

`.env` is git-ignored, so never commit it. Each teammate keeps their own.

## 5. Verify connectivity

```bash
apps/api/.venv/Scripts/python apps/api/scripts/check_services.py   # Windows
apps/api/.venv/bin/python apps/api/scripts/check_services.py       # macOS/Linux
```

Expected:

```
DATABASE_URL = postgresql+psycopg://vysel:***@localhost:5432/vysel
  ✓ PostgreSQL 15.x — database 'vysel' as 'vysel'
  ✓ PostgreSQL write/read round trip
REDIS_URL = redis://127.0.0.1:6379/0
  ✓ Redis-compatible server 7.x — PING, SET/GET round trip

All services reachable.
```

The write/read check runs in a transaction that is rolled back, so it leaves no data behind.

## 6. Run VYSEL

```powershell
.\start.ps1                 # Windows   (if scripts are blocked: powershell -ExecutionPolicy Bypass -File .\start.ps1)
./start.sh                  # macOS / Linux (first time: chmod +x start.sh)
```

The script runs preflight checks (tools, venv, `node_modules`, `.env`, free ports), checks PostgreSQL and Redis, applies migrations, then starts:

| Service | URL / command | Notes |
|---|---|---|
| **api** | <http://localhost:8000/docs> | FastAPI on Uvicorn |
| **worker** | Celery | Windows uses `--pool=solo` (prefork is unsupported there) |
| **web** | <http://localhost:3000> | Next.js; proxies `/api/v1/*` → API (same origin) |

Options: `-NoWeb` / `--no-web` runs the backend only. **Ctrl+C** stops all three.

### Verify the whole stack

```powershell
.\start.ps1 -Check          # ./start.sh --check
```

This boots everything, runs `apps/api/scripts/smoke_test.py`, then shuts down. The exit code is 0 on success:

```
✓ health ok — {'database': 'ok', 'cache': 'ok', 'queue': 'ok'}
✓ job job_… queued
✓ result from worker 'celery@<your-pc>': Hello, VYSEL!
✓ /api/v1 proxy reaches FastAPI (same-origin)
Smoke test passed — all services working together.
```

**Team checklist (Part 2.5):** each teammate runs `start.ps1 -Check` / `start.sh --check` on their own laptop and posts the final line in the team chat.

### Backend endpoints so far

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/health` | DB, cache and queue status; `503` if any is down |
| POST | `/v1/jobs/hello` | Queue the hello-world task → `202` + `Location` |
| GET | `/v1/jobs/{id}` | Job status (`queued → running → succeeded/failed`), read from PostgreSQL |

### Everyday commands (from `apps/api`, venv active)

```bash
pytest                                        # tests (SQLite + eager Celery; set TEST_DATABASE_URL for PostgreSQL)
ruff check . && ruff format --check .         # lint
alembic revision --autogenerate -m "add x"    # new migration after changing app/models.py
alembic upgrade head                          # apply migrations
```

## 7. CI (GitHub Actions)

`.github/workflows/ci.yml` runs on every push to `main` and every pull request, with no Docker:

- **API job:** ruff, then PostgreSQL (preinstalled on the runner) plus Redis (apt), then migration round trip and `alembic check`, then pytest against PostgreSQL, then a live smoke test (Uvicorn + Celery).
- **Web job:** Node 20, `npm ci`, design-system checks, type-check, `next build`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` on 5432 | Start PostgreSQL: Windows `Start-Service postgresql-x64-15` (elevated) · macOS `brew services start postgresql@15` · Linux `sudo systemctl start postgresql` |
| `password authentication failed for user "vysel"` | Re-run step 3 with the password that's in your `.env` |
| Jobs stay `queued`, smoke test "timed out" | Worker not running, or Redis URL uses `localhost` on Windows; use `127.0.0.1` |
| `Port 8000/3000 is in use` | Another dev server is running; stop it, or use `-NoWeb` if it's your own `next dev` |
| `Error 10061` / refused on 6379 | Start Redis: Windows `Start-Service Memurai` · macOS `brew services start redis` · Linux `sudo systemctl start redis-server` |
| Memurai stopped after ~10 days | Expected on the free Developer edition; restart the service |
| `python3.11: not found` | Use `py -3.11` on Windows, or install 3.11 as above |
