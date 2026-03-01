@echo off
echo Starting Neso Backend...
start "Neso Backend" cmd /k "cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo Starting Neso Frontend...
start "Neso Frontend" cmd /k "cd super-admin-panel && npm run dev"

echo Done. You should see two new windows pop up.
