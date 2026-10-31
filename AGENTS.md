# AGENTS.md

Guidance for AI coding agents working in this repo. Humans: see README.md and SETUP.md.

## What this is

A FastAPI app (Cue Voice Studio) that reads timed cue files and generates speech with Ming-3.0-tts-0.5B,
fits each line to its slot, and mixes a timeline WAV. Windows-first, NVIDIA GPU, Python 3.12.

## Layout

- `app.py`: API (`/api/status`, `/api/parse`, `/api/jobs`, `/api/jobs/{id}`, `/api/jobs/{id}/cancel`), single-worker job queue, `/files` serves `outputs/`.
- `engine.py`: `TTSEngine` (background model load), `fit_to_slot`, time-stretch (`tempo_python` WSOLA, `tempo_ffmpeg`, `change_tempo`), `mix_timeline`, WAV/zip/manifest writers.
- `cues.py`: parser, raises `CueError` with line-numbered messages.
- `static/index.html`: single-file UI, no build step.
- `check.py`: setup self-check; `package.py`: zip builder; `setup.bat` / `run.bat` / `run.ps1`: Windows scripts.
- `models/` (weights, gitignored except README) and `vendor/Ming-3.0-tts` (git submodule, do not edit).

## Run and verify

```bash
.venv\Scripts\python.exe check.py            # fast environment and file checks
.venv\Scripts\python.exe check.py --load     # also loads the model and speaks one line (~1 min, needs GPU)
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

There is no test suite. After changing `cues.py` or the fitting code, run `check.py` and a job with
`samples/sample.csv` (expected: 4 rows done, line 4 flagged padded, 18.0 s timeline).

## Rules and gotchas

- Do not commit weights, `.venv`, `.uvpython`, `outputs/` or zips. `.gitignore` covers them; check `git status` before committing.
- Never modify `vendor/Ming-3.0-tts`. It is pinned to commit `9332fb9`; bumping it needs a re-test and a `SETUP.md` update.
- Keep `torch`/`torchaudio` at 2.7.x built for CUDA 12.8 (`cu128`). The upstream repo pins torch 2.6, which has no kernels for RTX 50-series (sm_120). Keep Python at 3.12.
- Keep external executables optional. The portal must work with no ffmpeg (`MING_STRETCH=python`) and fall back by itself if ffmpeg cannot run. Do not add a hard dependency on any `.exe`.
- The model cannot target an exact duration. Fitting is done by time-stretching within `min_tempo`/`max_tempo`, with `too_long` / `padded` flags. Do not silently hide those flags.
- Text normalization is off (`pynini` not installed); only plain numbers are expanded. Do not assume dates or symbols are read correctly.
- Large cue input is capped (`MAX_CUES`, `MAX_TEXT_CHARS` in `cues.py`). Keep the limits and the error messages user-readable.
- Gmail blocks `.bat` even in zips, so `package.py` also builds an email-safe zip with scripts stored as `.txt`. Keep the scripts as normal `.bat` / `.ps1` in the repo.
- If you change setup steps, versions or checks, update `SETUP.md`, `check.py` and `setup.bat` together so they stay consistent. Expected sizes in `check.py`: `model.safetensors` 2,959,055,504 bytes, `campplus.onnx` 28,303,423 bytes.

## Style

- Match the surrounding code: plain Python, type hints sparingly, short comments only where the reason is not obvious.
- UI is one HTML file with CSS variables for light and dark themes; keep it dependency-free.
- Use `localhost` binding (`127.0.0.1`) only; this is a local tool with no authentication.
