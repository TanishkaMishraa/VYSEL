<#
.SYNOPSIS
  Start VYSEL locally on Windows: API (FastAPI/Uvicorn), worker (Celery) and web (Next.js).

.DESCRIPTION
  1. Preflight: tools, virtualenv, node_modules, apps/api/.env, free ports
  2. Verifies PostgreSQL and Redis (Memurai) are reachable
  3. Applies database migrations (alembic upgrade head)
  4. Runs all three services with labelled logs. Ctrl+C stops everything.

.PARAMETER Check
  Start everything, run the end-to-end smoke test, then shut down. Exit code = result.
.PARAMETER NoWeb
  Skip the Next.js app (backend only).

.EXAMPLE
  .\start.ps1            # develop
  .\start.ps1 -Check     # verify the whole stack works
#>
param([switch]$Check, [switch]$NoWeb)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Api = Join-Path $PSScriptRoot 'apps\api'
$Py = Join-Path $Api '.venv\Scripts\python.exe'

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "  x $msg" -ForegroundColor Red; exit 1 }
function Ok($msg) { Write-Host "  + $msg" -ForegroundColor Green }

Step 'Preflight'
foreach ($tool in 'node', 'npm') { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "$tool not found. Install Node.js 20 or 22 (see docs/local-setup.md)." } }
$nodeMajor = [int]((node -v) -replace '^v(\d+).*', '$1')
if ($nodeMajor -lt 20) { Fail "Node $(node -v) is unsupported; use Node 20 or higher." }
Ok "Node $(node -v)"

if (-not (Test-Path $Py)) {
  Write-Host '  Creating Python 3.11 virtualenv...'
  & py -3.11 -m venv (Join-Path $Api '.venv'); if ($LASTEXITCODE) { Fail 'Python 3.11 not found (py -3.11). See docs/local-setup.md.' }
}
# Re-sync dependencies whenever their manifests change (e.g. after git pull), not only on first run.
function DepsHash($files) { ($files | ForEach-Object { (Get-FileHash $_ -Algorithm SHA256).Hash }) -join '' }
$pyStamp = Join-Path $Api '.venv\.deps-hash'
$pyHash = DepsHash @((Join-Path $Api 'requirements.txt'), (Join-Path $Api 'requirements-dev.txt'))
if (-not (Test-Path $pyStamp) -or (Get-Content $pyStamp -Raw) -ne $pyHash) {
  Write-Host '  Installing Python packages (requirements changed)...'
  & $Py -m pip install --disable-pip-version-check -q -r (Join-Path $Api 'requirements-dev.txt'); if ($LASTEXITCODE) { Fail 'pip install failed.' }
  Set-Content -Path $pyStamp -Value $pyHash -NoNewline
}
Ok "Python $((& $Py --version) -replace 'Python ', '') (apps/api/.venv, dependencies in sync)"

$npmStamp = 'node_modules\.deps-hash'
$npmHash = DepsHash @('package-lock.json')
if (-not (Test-Path $npmStamp) -or (Get-Content $npmStamp -Raw) -ne $npmHash) {
  Write-Host '  Installing npm packages (lockfile changed)...'
  npm install --no-audit --no-fund; if ($LASTEXITCODE) { Fail 'npm install failed.' }
  Set-Content -Path $npmStamp -Value $npmHash -NoNewline
}
Ok 'node_modules in sync with package-lock.json'

if (-not (Test-Path (Join-Path $Api '.env'))) {
  Copy-Item (Join-Path $Api '.env.example') (Join-Path $Api '.env')
  Fail 'Created apps/api/.env from the template. Set your database password in it, then re-run.'
}
Ok 'apps/api/.env present'

& $Py (Join-Path $Api 'scripts\setup_face_analysis.py'); if ($LASTEXITCODE) { Fail 'Face analysis setup failed (MediaPipe + model, see above).' }

$ports = @(8000) + $(if (-not $NoWeb) { 3000 } else { @() })
foreach ($port in $ports) {
  $owner = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($owner) { Fail "Port $port is in use by PID $($owner.OwningProcess) ($((Get-Process -Id $owner.OwningProcess).ProcessName)). Stop it first." }
}
Ok "Ports free: $($ports -join ', ')"

Step 'Checking PostgreSQL and Redis'
$env:PYTHONIOENCODING = 'utf-8'
& $Py (Join-Path $Api 'scripts\check_services.py')
if ($LASTEXITCODE) { Fail 'Services unreachable. Start them (elevated): Start-Service postgresql-x64-15; Start-Service Memurai' }

Step 'Applying database migrations'
Push-Location $Api
try { & $Py -m alembic upgrade head; if ($LASTEXITCODE) { Fail 'Migration failed.' } } finally { Pop-Location }
Ok 'Database at latest revision'

# Windows needs --pool=solo: Celery's prefork pool is unsupported there.
$apiCmd = "`"$Py`" -m uvicorn app.main:app --app-dir apps/api --port 8000"
$workerCmd = "`"$Py`" -m celery --workdir apps/api -A app.worker worker --pool=solo --loglevel=INFO"
$webCmd = 'npm run dev -w @vysel/web'

if ($Check) {
  Step 'Starting services for the smoke test'
  $logs = Join-Path $PSScriptRoot '.logs'; New-Item -ItemType Directory -Force $logs | Out-Null
  $procs = @()
  $procs += Start-Process -FilePath $Py -ArgumentList '-m', 'uvicorn', 'app.main:app', '--app-dir', 'apps/api', '--port', '8000' -PassThru -WindowStyle Hidden -RedirectStandardOutput "$logs\api.out.log" -RedirectStandardError "$logs\api.log"
  $procs += Start-Process -FilePath $Py -ArgumentList '-m', 'celery', '--workdir', 'apps/api', '-A', 'app.worker', 'worker', '--pool=solo', '--loglevel=INFO' -PassThru -WindowStyle Hidden -RedirectStandardOutput "$logs\worker.out.log" -RedirectStandardError "$logs\worker.log"
  if (-not $NoWeb) { $procs += Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $webCmd -PassThru -WindowStyle Hidden -RedirectStandardOutput "$logs\web.log" -RedirectStandardError "$logs\web.err.log" }
  try {
    $smokeArgs = @((Join-Path $Api 'scripts\smoke_test.py'), '--timeout', '60') + $(if (-not $NoWeb) { '--web', 'http://localhost:3000' } else { @() })
    & $Py @smokeArgs
    $code = $LASTEXITCODE
  } finally {
    Step 'Stopping services'
    foreach ($p in $procs) { if (-not $p.HasExited) { taskkill /PID $p.Id /T /F | Out-Null } }
    Ok "Stopped. Logs in .logs\"
  }
  exit $code
}

Step 'Starting VYSEL  (Ctrl+C stops everything)'
Write-Host '  API     http://localhost:8000/docs'
if (-not $NoWeb) { Write-Host '  Web     http://localhost:3000' }
$names = 'api,worker' + $(if (-not $NoWeb) { ',web' } else { '' })
$cmds = @($apiCmd, $workerCmd) + $(if (-not $NoWeb) { $webCmd } else { @() })
npx concurrently --kill-others-on-fail --names $names --prefix-colors 'magenta,yellow,cyan' @cmds
