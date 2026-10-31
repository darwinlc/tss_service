"""Setup self-check.  Usage:  .venv\\Scripts\\python.exe check.py [--load]

Without --load it only inspects the environment and files (fast, no GPU use).
With --load it also loads the model and synthesizes one short line (about a minute).
"""

import importlib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

failures = 0


def report(ok, label, detail="", warn=False):
    global failures
    mark = "PASS" if ok else ("WARN" if warn else "FAIL")
    if not ok and not warn:
        failures += 1
    print(f"[{mark}] {label}" + (f" - {detail}" if detail else ""))


def section(title):
    print(f"\n== {title}")


# -- Python and packages ------------------------------------------------------
section("Python and packages")
report(sys.version_info[:2] == (3, 12), "Python 3.12", sys.version.split()[0],
       warn=sys.version_info[:2] != (3, 12))
report(Path(sys.prefix).name == ".venv" or (ROOT / ".venv").exists(),
       "Running inside the project .venv", sys.executable, warn=True)

expected = {
    "torch": "2.7.1", "torchaudio": "2.7.1", "transformers": "4.46.3",
    "tokenizers": "0.20.3", "diffusers": "0.33.0", "accelerate": "1.3.0",
    "fastapi": None, "uvicorn": None, "soundfile": "0.12.1", "onnxruntime": None,
    "x_transformers": None, "multipart": None,
}
for name, wanted in expected.items():
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "?")
        ok = wanted is None or str(version).startswith(wanted)
        report(ok, f"import {name}", f"{version}" + ("" if ok else f" (expected {wanted})"))
    except Exception as error:
        report(False, f"import {name}", f"{type(error).__name__}: {error}")

# -- GPU -----------------------------------------------------------------------
section("GPU")
try:
    import torch

    report("+cu" in torch.__version__, "PyTorch is a CUDA build", torch.__version__)
    available = torch.cuda.is_available()
    report(available, "CUDA available to PyTorch",
           "" if available else "no GPU: update the NVIDIA driver or reinstall torch from the cu128 index",
           warn=False)
    if available:
        props = torch.cuda.get_device_properties(0)
        capability = f"sm_{props.major}{props.minor}"
        report(capability in torch.cuda.get_arch_list(),
               f"{props.name} ({capability}) is supported by this PyTorch build",
               ", ".join(torch.cuda.get_arch_list()))
        gib = props.total_memory / 2**30
        report(gib >= 6, "At least 6 GB of GPU memory", f"{gib:.1f} GiB", warn=True)
except Exception as error:
    report(False, "torch check", f"{type(error).__name__}: {error}")

# -- ffmpeg --------------------------------------------------------------------
section("Time-stretch (ffmpeg is optional)")
try:
    import numpy as np
    import engine

    tone = (0.3 * np.sin(2 * np.pi * 220 * np.arange(44100 * 2) / 44100)).astype(np.float32)
    built_in = engine.tempo_python(tone, 44100, 1.25)
    report(abs(len(built_in) / 44100 - 1.6) < 0.01, "Built-in stretcher works (no executables)",
           f"2.00s -> {len(built_in) / 44100:.2f}s at 1.25x")
    exe = engine.ffmpeg_exe()
    if exe is None:
        print("[INFO] ffmpeg not present: the built-in stretcher will be used.")
    else:
        try:
            out = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=20)
            report(out.returncode == 0, "ffmpeg found and runs (used automatically)",
                   out.stdout.splitlines()[0] if out.stdout else exe, warn=True)
        except OSError as error:
            report(False, "ffmpeg found but cannot run (will fall back to built-in)", str(error), warn=True)
    print(f"      active method: {engine.stretch_method()}")
except Exception as error:
    report(False, "time-stretch", f"{type(error).__name__}: {error}")

# -- Files ---------------------------------------------------------------------
section("Model weights and repo")
try:
    import engine

    model, repo = engine.MODEL_PATH, engine.VENDOR_PATH
    print(f"      model dir: {model}\n      repo dir : {repo}")
    sizes = {"model.safetensors": 2_959_055_504, "campplus.onnx": 28_303_423}
    for name in ("config.json", "configuration.json", "tokenizer.json", "tokenizer_config.json",
                 "vocab.json", "merges.txt", "added_tokens.json", "special_tokens_map.json",
                 "model.safetensors", "campplus.onnx"):
        path = model / name
        if not path.is_file():
            report(False, f"weights: {name}", "missing")
        elif name in sizes:
            report(path.stat().st_size == sizes[name], f"weights: {name}",
                   f"{path.stat().st_size:,} bytes" + ("" if path.stat().st_size == sizes[name]
                                                         else f" (expected {sizes[name]:,}: incomplete download?)"))
        else:
            report(True, f"weights: {name}")
    for name in ("ming_tts.py", "tts_tasks.py", "modeling_bailingmm.py", "spkemb_extractor.py",
                 "frontend/number_en.py", "audio_tokenizer", "fm"):
        report((repo / name).exists(), f"repo: {name}", "" if (repo / name).exists() else "missing")
except Exception as error:
    report(False, "file check", f"{type(error).__name__}: {error}")

# -- Port ----------------------------------------------------------------------
section("Port")
with socket.socket() as sock:
    free = sock.connect_ex(("127.0.0.1", 8000)) != 0
report(free, "Port 8000 is free", "" if free else "something is already listening (is the portal running?)",
       warn=True)

# -- Optional model load -------------------------------------------------------
if "--load" in sys.argv:
    section("Model load and one synthesis")
    try:
        import torch

        tts = engine.TTSEngine()
        started = time.time()
        tts._load()
        report(tts.state == "ready", "Model loads", f"{time.time() - started:.0f}s on {tts.device}" if tts.state == "ready" else tts.error)
        if tts.state == "ready":
            started = time.time()
            samples = tts.synthesize("Hello, this is a setup test.", "US_Emma")
            seconds = len(samples) / tts.sample_rate
            report(0.5 < seconds < 10, "Synthesizes a short line",
                   f"{seconds:.1f}s of audio in {time.time() - started:.1f}s")
            if torch.cuda.is_available():
                print(f"      peak GPU memory: {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
    except Exception as error:
        report(False, "model load", f"{type(error).__name__}: {error}")
else:
    print("\n(Tip: run with --load to also load the model and synthesize one line.)")

print("\nALL REQUIRED CHECKS PASSED" if failures == 0 else f"\n{failures} REQUIRED CHECK(S) FAILED")
sys.exit(1 if failures else 0)
