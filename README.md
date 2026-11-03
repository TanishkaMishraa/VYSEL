# VYSEL

AI-powered personal styling: style advice built from your face, not a trend list.
Team Terrificers · PSIT Kanpur.

## Quick start

1. Install Python 3.11, Node 20/22, PostgreSQL 15 and Redis (Memurai on Windows). See **[docs/local-setup.md](docs/local-setup.md)**.
2. Create the database and copy the config:
   ```bash
   psql -h localhost -U postgres -v app_password='…' -f apps/api/scripts/create_db.sql
   cp apps/api/.env.example apps/api/.env      # then set the password
   ```
3. Start everything:
   ```powershell
   .\start.ps1          # Windows        (verify: .\start.ps1 -Check)
   ./start.sh           # macOS / Linux  (verify: ./start.sh --check)
   ```
   Web <http://localhost:3000> · API docs <http://localhost:8000/docs>

## Repository

| Path | What |
|---|---|
| `apps/web` | Next.js 14 landing page and app ([docs/landing-page.md](docs/landing-page.md)) |
| `apps/api` | FastAPI + SQLAlchemy/Alembic + Celery worker |
| `packages/ui` | Design system: tokens, components, brand assets, showcase |
| `docs/api/openapi.yaml` | API contract |
| `.github/workflows/ci.yml` | Lint, tests, migrations, smoke test, web build |

No Docker: everything runs natively.
