# Cue Voice Studio: setup guide for a new Windows machine

A local web page: upload a cue file (`start, duration, text`) and get speech from the
open-weight **Ming-3.0-tts-0.5B** model, fitted to each slot and mixed onto one timeline.

Everything runs on your own machine. After setup, no internet is needed.

## 0. What you need

| Item | Requirement |
| --- | --- |
| OS | Windows 10 or 11, 64-bit |
| GPU | NVIDIA, 6 GB+ video memory (built and tested on an RTX 5060 8 GB; the model used ~3.9 GB) |
| NVIDIA driver | Recent enough for CUDA 12.8: `nvidia-smi` should report **CUDA Version 12.8 or higher** |
| Python | **3.12** (64-bit). Not 3.13 or 3.14: some pinned packages have no wheels for them |
| Disk | About 15 GB free (3 GB weights, 5 GB PyTorch, the rest packages and outputs) |
| Git | Optional. You can download ZIPs from the browser instead |

Without an NVIDIA GPU the code falls back to the CPU, but I have not tested that and it will be very slow.

## 1. Unzip the package

Unzip `ming-tts-portal-package.zip` somewhere with a short path, for example `C:\tools\`.
You should get:

```
C:\tools\ming-tts-portal\
    app.py  cues.py  engine.py  check.py  requirements.txt  requirements-optional.txt
    setup.bat  run.bat  run.ps1  SETUP.md
    static\  samples\  models\  vendor\
```

Avoid folders that are synced (OneDrive) or have very long names.

## 2. Install Python 3.12

1. Download Python 3.12 (64-bit) from https://www.python.org/downloads/windows/
2. In the installer tick **"Use py launcher"** (and optionally "Add python.exe to PATH").
3. Check in a new terminal:

```bash
py -3.12 --version
```

It must print `Python 3.12.x`.

## 3. Download the Ming-3.0-tts code (GitHub)

The weights alone cannot run. The model needs the authors' inference code.

**Option 0, if you cloned this portal from GitHub:** the authors' repo is a git submodule pinned to the
tested commit. Fetch it with:

```bash
git submodule update --init
```

(or clone with `git clone --recurse-submodules`). Then skip to step 4.

**Option A, with git** (run from `C:\tools\ming-tts-portal`):

```bash
git clone https://github.com/inclusionAI/Ming-3.0-tts.git vendor/Ming-3.0-tts
git -C vendor/Ming-3.0-tts checkout 9332fb9443325d4726ce02cefd4ec1c211df4079
```

**Option B, no git:** download
https://github.com/inclusionAI/Ming-3.0-tts/archive/9332fb9443325d4726ce02cefd4ec1c211df4079.zip
and extract it. Rename the extracted folder to `Ming-3.0-tts` and move it so that this file exists:

```
ming-tts-portal\vendor\Ming-3.0-tts\ming_tts.py
```

The commit above is the version this portal was tested against. A newer commit may work but is untested.

## 4. Download the model weights (Hugging Face)

Page: https://huggingface.co/inclusionAI/Ming-3.0-tts-0.5B/tree/main (MIT license, not gated, no login needed).
Tested revision: `7247f4c94a5b2e987404ed28a5cfec41b1a4ca61`.

Put **all files** in this folder (create it):

```
ming-tts-portal\models\Ming-3.0-tts-0.5B\
```

**Option A, browser:** on the "Files and versions" tab, download each file (download icon next to its name).
The big one is `model.safetensors` (**2,959,055,504 bytes**, about 2.8 GB). Direct link:
https://huggingface.co/inclusionAI/Ming-3.0-tts-0.5B/resolve/main/model.safetensors

**Option B, command line** (after step 5, using the project Python):

```bash
.venv\Scripts\python.exe -m pip install huggingface_hub
.venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('inclusionAI/Ming-3.0-tts-0.5B', revision='7247f4c94a5b2e987404ed28a5cfec41b1a4ca61', local_dir=r'models\Ming-3.0-tts-0.5B')"
```

The loader reads these files (the figures, README and PDF are not needed, but downloading everything is fine):

`config.json`, `configuration.json`, `model.safetensors`, `campplus.onnx`, `tokenizer.json`,
`tokenizer_config.json`, `vocab.json`, `merges.txt`, `added_tokens.json`, `special_tokens_map.json`

A browser download that stops early leaves a smaller `model.safetensors`; step 6 catches that.

## 5. Install dependencies

Double-click **`setup.bat`** (or run it in a terminal). It creates `.venv`, installs PyTorch 2.7.1 for
CUDA 12.8 (about 3 GB), installs `requirements.txt`, then the optional `requirements-optional.txt`
(see "ffmpeg is optional" below), then runs the checks. Expect 5 to 15 minutes.

PyTorch **2.7 or newer with CUDA 12.8** is required for RTX 50-series (Blackwell) cards. The repo's own
`requirements.txt` pins torch 2.6, which does not work on them. Do not use it.

## 6. Verify the setup

```bash
.venv\Scripts\python.exe check.py
```

Every line should say `PASS`, ending with `ALL REQUIRED CHECKS PASSED`. What each group verifies:

| Check | Why it matters |
| --- | --- |
| Python 3.12 | Other versions can fail to install pinned packages |
| `import torch` shows `+cu128`, CUDA available | A CPU-only torch installs silently if the cu128 index was skipped |
| GPU architecture is in the PyTorch arch list | Otherwise you get "no kernel image is available" at run time |
| `model.safetensors` is 2,959,055,504 bytes | Catches truncated downloads |
| `campplus.onnx` is 28,303,423 bytes | Speaker model |
| Repo has `ming_tts.py`, `frontend\number_en.py`, `audio_tokenizer`, `fm` | Catches a wrong folder level after unzipping |
| Port 8000 is free | Another copy may already be running |

Then do the real test, which loads the model and speaks one line (about a minute):

```bash
.venv\Scripts\python.exe check.py --load
```

Expected (my machine): `Model loads` on `cuda:0` in about 7 s, `Synthesizes a short line` of about 2.5 s of audio,
and peak GPU memory around 3 GiB. Warnings about `flash-attn`, `past_key_values` and "model of type dense" are
normal and can be ignored.

## 7. Run the portal

Double-click **`run.bat`** (or `run.ps1`). Wait until the page shows a green **"Model ready (cuda:0)"**
(about a minute on first load). Then open http://127.0.0.1:8000

Smoke test:
1. Drop `samples\sample.csv` on the page (4 cues).
2. Voice `US_Emma`, defaults for speed limits, click **Generate audio**.
3. Expected: 4 rows turn "Done"; line 4 is flagged "padded"; a timeline of **18.0 s** appears with
   download buttons. Files land in `outputs\<job id>\`.

Stop the server with Ctrl+C in its window (or close the window).

## Cue file format

CSV with an optional header:

```
start,duration,text
0.5,4.0,"Welcome to the demo."
5.0,3.5,"First, we set up the scene."
```

or pipe-separated text (lines starting with `#` are ignored):

```
00:00.5 | 4.0 | Welcome to the demo.
00:05.0 | 3.5 | First, we set up the scene.
```

Times are seconds (`4.5`) or clock style (`1:04.5`). Up to 300 cues, 1000 characters each, UTF-8.

## How fitting works (so the results make sense)

The model cannot target an exact length. Each line is spoken naturally, then sped up or slowed down
(pitch preserved) to fill its duration, but only within the limits on the page (default 0.9x to 1.3x).

- Too long even at the fastest allowed speed: the audio is kept whole and flagged **too long**. Shorten the
  text or lengthen the duration.
- Too short even at the slowest allowed speed: padded with silence and flagged **padded**.

## ffmpeg is optional (restricted environments)

The speed change can be done two ways, and the portal picks one automatically:

| Method | When it is used | Runs an external `.exe`? |
| --- | --- | --- |
| `ffmpeg` | `imageio-ffmpeg` is installed (or `ffmpeg` is on PATH) | Yes, `ffmpeg.exe` from the wheel |
| `python` | No ffmpeg found, `MING_STRETCH=python` is set, or running ffmpeg fails | No, numpy only (WSOLA) |

If ffmpeg is present but cannot be launched (blocked by policy), the portal falls back to `python` by itself.
Hover the green "Model ready" pill to see the active method; it is also recorded as `stretch_method` in
`manifest.json` and shown by `check.py`.

For a locked-down machine: skip `requirements-optional.txt` (remove that step from `setup.bat`) or set
`MING_STRETCH=python` before `run.bat`. The only other binaries are native libraries inside the pip wheels
(PyTorch, onnxruntime, numpy, soundfile) and the NVIDIA driver.

In my test the built-in method preserved pitch and length and tracked ffmpeg's output closely (spectral
correlation about 0.94), but I could not listen to it. Check a few lines by ear, especially at 1.3x.

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `py -3.12` not found | Python 3.12 not installed, or "py launcher" unticked. Reinstall it |
| check.py: CUDA not available | Update the NVIDIA driver, then confirm `torch.__version__` ends in `+cu128`. If not: `.venv\Scripts\python.exe -m pip install --force-reinstall torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128` |
| "no kernel image is available" | Installed torch is older than your GPU. Use the cu128 build above |
| `model.safetensors` size mismatch | Incomplete download. Download it again |
| Pill stays red: "Model failed to load" | Hover it for the error. Usually a wrong folder (step 3 or 4) or out of GPU memory: close other GPU apps |
| CUDA out of memory | Other programs are using the GPU. The model itself needs about 4 GB |
| Port 8000 already in use | Close the other copy, or edit the port in `run.bat` |
| Weights or repo kept elsewhere | Set `MING_MODEL_PATH` and `MING_REPO_PATH` environment variables to those folders before running `run.bat` |
| Numbers read oddly | Only plain numbers are expanded (`pynini` is not installed). Write dates and symbols out as words |

## Notes

- Built-in voices are English: US_Emma, UK_George, UK_Charlotte.
- Label synthetic speech as synthetic where it could be mistaken for a real recording (see the model's usage
  disclaimer on its Hugging Face page). The model and code are MIT licensed.
- Tested versions: Python 3.12.16, torch 2.7.1+cu128, transformers 4.46.3, on Windows 11 with an RTX 5060.
