@echo off
rem One-time setup: creates .venv (Python 3.12), installs PyTorch (CUDA 12.8) and the other
rem dependencies, then runs check.py. Run it from the portal folder after you have put the
rem model weights in models\ and the Ming-3.0-tts repo in vendor\ (see SETUP.md).
cd /d "%~dp0"

py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo [FAIL] Python 3.12 was not found. Install it from https://www.python.org/downloads/ and tick "py launcher".
  pause & exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3.12 -m venv .venv
  if errorlevel 1 ( echo [FAIL] Could not create .venv & pause & exit /b 1 )
)

set PY=.venv\Scripts\python.exe
%PY% -m pip install --upgrade pip
if errorlevel 1 ( echo [FAIL] pip upgrade failed & pause & exit /b 1 )

echo Installing PyTorch 2.7.1 for CUDA 12.8 (about 3 GB)...
%PY% -m pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple
if errorlevel 1 ( echo [FAIL] PyTorch install failed & pause & exit /b 1 )

echo Installing the other dependencies...
%PY% -m pip install -r requirements.txt
if errorlevel 1 ( echo [FAIL] requirements install failed & pause & exit /b 1 )

rem Optional: bundled ffmpeg.exe. Delete or skip these lines where executables are restricted.
echo Installing optional ffmpeg wheel (the portal also works without it)...
%PY% -m pip install -r requirements-optional.txt
if errorlevel 1 echo [WARN] Optional ffmpeg wheel not installed; the built-in time-stretcher will be used.

echo.
echo Running checks...
%PY% check.py
pause
