#!/usr/bin/env bash
# Start VYSEL locally on Linux/macOS: API (FastAPI/Uvicorn), worker (Celery), web (Next.js).
#
#   ./start.sh            develop — labelled logs, Ctrl+C stops everything
#   ./start.sh --check    start everything, run the end-to-end smoke test, shut down
#   ./start.sh --no-web   backend only
#
# Steps: preflight → PostgreSQL/Redis check → alembic upgrade head → run services.
set -euo pipefail
cd "$(dirname "$0")"

CHECK=0; NO_WEB=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    --no-web) NO_WEB=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg"; exit 2 ;;
  esac
done

API=apps/api
PY="$API/.venv/bin/python"
step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m+\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mx %s\033[0m\n' "$1"; exit 1; }

step "Preflight"
command -v node >/dev/null || fail "node not found. Install Node.js 20 or 22 (docs/local-setup.md)."
NODE_MAJOR=$(node -p 'process.versions.node.split(".")[0]')
{ [ "$NODE_MAJOR" -ge 20 ] && [ "$NODE_MAJOR" -le 22 ]; } || fail "Node $(node -v) is unsupported; use Node 20 or 22."
ok "Node $(node -v)"

if [ ! -x "$PY" ]; then
  command -v python3.11 >/dev/null || fail "python3.11 not found (docs/local-setup.md)."
  echo "  Creating Python 3.11 virtualenv..."
  python3.11 -m venv "$API/.venv"
  "$PY" -m pip install --disable-pip-version-check -q -r "$API/requirements-dev.txt"
fi
ok "Python $("$PY" -c 'import platform; print(platform.python_version())') ($API/.venv)"

[ -d node_modules ] || { echo "  Installing npm packages..."; npm install --no-audit --no-fund; }
ok "node_modules present"

if [ ! -f "$API/.env" ]; then
  cp "$API/.env.example" "$API/.env"
  fail "Created $API/.env from the template. Set your database password in it, then re-run."
fi
ok "$API/.env present"

PORTS="8000"; [ "$NO_WEB" = 1 ] || PORTS="8000 3000"
for port in $PORTS; do
  if command -v lsof >/dev/null && lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    fail "Port $port is in use (PID $(lsof -iTCP:"$port" -sTCP:LISTEN -t | head -1)). Stop it first."
  fi
done
ok "Ports free: $PORTS"

step "Checking PostgreSQL and Redis"
"$PY" "$API/scripts/check_services.py" || fail "Services unreachable. macOS: brew services start postgresql@15 redis · Linux: sudo systemctl start postgresql redis-server"

step "Applying database migrations"
(cd "$API" && .venv/bin/python -m alembic upgrade head) || fail "Migration failed."
ok "Database at latest revision"

API_CMD="$PY -m uvicorn app.main:app --app-dir $API --port 8000"
WORKER_CMD="$PY -m celery --workdir $API -A app.worker worker --loglevel=INFO --concurrency=2"
WEB_CMD="npm run dev -w @vysel/web"

if [ "$CHECK" = 1 ]; then
  step "Starting services for the smoke test"
  mkdir -p .logs
  set -m  # each background job gets its own process group, so we can stop whole trees
  PIDS=()
  $API_CMD >.logs/api.log 2>&1 & PIDS+=($!)
  $WORKER_CMD >.logs/worker.log 2>&1 & PIDS+=($!)
  [ "$NO_WEB" = 1 ] || { $WEB_CMD >.logs/web.log 2>&1 & PIDS+=($!); }
  cleanup() {
    step "Stopping services"
    for pid in "${PIDS[@]}"; do kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
    ok "Stopped. Logs in .logs/"
  }
  trap cleanup EXIT
  SMOKE_ARGS=(--timeout 60); [ "$NO_WEB" = 1 ] || SMOKE_ARGS+=(--web http://localhost:3000)
  "$PY" "$API/scripts/smoke_test.py" "${SMOKE_ARGS[@]}"
  exit $?
fi

step "Starting VYSEL  (Ctrl+C stops everything)"
echo "  API     http://localhost:8000/docs"
NAMES="api,worker"; CMDS=("$API_CMD" "$WORKER_CMD")
[ "$NO_WEB" = 1 ] || { echo "  Web     http://localhost:3000"; NAMES="$NAMES,web"; CMDS+=("$WEB_CMD"); }
exec npx concurrently --kill-others-on-fail --names "$NAMES" --prefix-colors "magenta,yellow,cyan" "${CMDS[@]}"
