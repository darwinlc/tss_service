# Cue Voice Studio

A local web page that turns a cue file into speech. Upload `start, duration, text` lines, pick a
built-in voice, and get one WAV per line plus a single timeline WAV with every line placed at its
start time. Speech comes from the open-weight
[Ming-3.0-tts-0.5B](https://huggingface.co/inclusionAI/Ming-3.0-tts-0.5B) model, running on your own GPU.

Built for the "silent video, then timed narration, then overlay the audio" workflow (for example with Remotion).

## How it works

- Each line is spoken naturally, then sped up or slowed down (pitch preserved) to fill its duration,
  within limits you set (default 0.9x to 1.3x).
- A line that is too long even at the fastest allowed speed is kept whole and flagged **too long**.
  One that is too short is padded with silence and flagged **padded**.
- Time-stretching uses a built-in numpy method (WSOLA) with no external programs. If `ffmpeg` is
  available (the optional `imageio-ffmpeg` wheel or one on PATH) it is used automatically instead.

## Quick start (Windows)

You need Windows 10/11, an NVIDIA GPU with 6 GB+ memory, and Python 3.12. The full guide with
checks is in [SETUP.md](SETUP.md). In short:

```bash
git clone --recurse-submodules https://github.com/darwinlc/tss_service.git
cd tss_service
```

1. Download the model weights into `models/Ming-3.0-tts-0.5B/` (see [models/README.md](models/README.md)).
2. Run `setup.bat` (creates `.venv`, installs PyTorch for CUDA 12.8 and the other packages).
3. Run `.venv\Scripts\python.exe check.py`, then `run.bat`.
4. Open http://127.0.0.1:8000 and drop `samples/sample.csv` on the page.

## Cue file format

CSV with an optional header, or pipe/tab separated. Times are seconds (`4.5`, `4.5s`) or clock style
(`1:04.5`, `0:01:04`). Lines starting with `#` are ignored. Up to 300 cues, 1000 characters each.

```
start,duration,text
0.5,4.0,"Welcome to the demo."
5.0,3.5,"First, we set up the scene."
```

## Output

Each job writes to `outputs/<job id>/`: `line_NNN.wav`, `timeline.wav`, `manifest.json`
(timings, tempo used, flags, stretch method) and `all_audio.zip`.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | FastAPI server and job queue |
| `engine.py` | Model loading, synthesis, fitting, time-stretch, mixing |
| `cues.py` | Cue file parser |
| `static/index.html` | The web page |
| `check.py` | Setup self-check (`--load` also runs the model) |
| `package.py` | Builds distribution zips (plus an email-safe one with scripts stored as `.txt`) |
| `models/` | Weights go here (not in git) |
| `vendor/Ming-3.0-tts` | Authors' inference code, a git submodule pinned to the tested commit |

## Licensing and use

The portal code is yours to license as you see fit (no license file is set yet). The Ming-3.0-tts model and
code are MIT licensed. Label synthetic speech as synthetic where it could be mistaken for a real recording;
see the model's usage notes on Hugging Face.
