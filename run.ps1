# Start the portal at http://127.0.0.1:8000 (the model loads in the background).
Set-Location $PSScriptRoot
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
