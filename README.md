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
| `apps/web` | Next.js 14 landing page, dashboard, scan setup, onboarding and account settings ([docs/landing-page.md](docs/landing-page.md)) |
| `apps/api` | FastAPI auth/profile API + SQLAlchemy/Alembic + Celery worker |
| `packages/ui` | Design system: tokens, components, brand assets, showcase |
| `docs/api/openapi.yaml` | API contract |
| `.github/workflows/ci.yml` | Lint, tests, migrations, smoke test, web build |

No Docker: everything runs natively.

After signing up, users can complete `/onboarding`; their style goals, preferred occasions, budget and style preferences are saved to their profile. The signed-in app is available at `/dashboard`, with editable account and preference settings at `/settings`. `/scan` currently provides a local-only photo preview; upload and analysis are not available yet.
