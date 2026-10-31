@echo off
rem Start the portal at http://127.0.0.1:8000 (the model loads in the background).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [FAIL] .venv not found. Run setup.bat first.
  pause & exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
