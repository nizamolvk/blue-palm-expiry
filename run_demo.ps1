# Starts the local demo: reminder drafts on http://localhost:8000/docs
# Uses the demo keys and a local SQLite file. Does not use Postgres.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    python -m venv .venv
}

& $python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

$env:API_KEY = "dev-api-key-change-me"
$env:MANAGER_API_KEY = "manager-key-change-me"
$env:APP_ENV = "development"
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

& $python -c @"
from task2_api.database import Base, make_engine, make_session_factory
from task2_api.load_data import load_csv
import task4_agent.models
from task4_agent.reminder_agent import run

engine = make_engine()
Base.metadata.create_all(engine)
session = make_session_factory(engine)()
try:
    load_csv(session)
    run(session)
finally:
    session.close()
"@

Write-Host "Demo is starting. Open http://localhost:8000/docs"
Write-Host "Read key: dev-api-key-change-me"
Write-Host "Approve or reject key: manager-key-change-me"

& $python -m uvicorn task4_agent.main:app --port 8000
