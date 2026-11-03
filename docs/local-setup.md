# Local Development Setup — Parts 2.1 & 2.2

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
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

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
REDIS_URL = redis://localhost:6379/0
  ✓ Redis-compatible server 7.x — PING, SET/GET round trip

All services reachable.
```

The write/read check runs in a transaction that is rolled back, so it leaves no data behind.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` on 5432 | Start PostgreSQL: Windows `Start-Service postgresql-x64-15` (elevated) · macOS `brew services start postgresql@15` · Linux `sudo systemctl start postgresql` |
| `password authentication failed for user "vysel"` | Re-run step 3 with the password that's in your `.env` |
| `Error 10061` / refused on 6379 | Start Redis: Windows `Start-Service Memurai` · macOS `brew services start redis` · Linux `sudo systemctl start redis-server` |
| Memurai stopped after ~10 days | Expected on the free Developer edition; restart the service |
| `python3.11: not found` | Use `py -3.11` on Windows, or install 3.11 as above |
