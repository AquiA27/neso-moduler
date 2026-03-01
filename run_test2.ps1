cd c:\Users\alibu\NesoModuler\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 | Out-File -FilePath c:\Users\alibu\NesoModuler\backend_log.txt -Encoding utf8
