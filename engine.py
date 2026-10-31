"""Ming-3.0-tts wrapper plus the audio fitting and timeline mixing helpers."""

import functools
import json
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent


def _locate(env_name, *candidates):
    """Env var wins; otherwise the first candidate that exists."""
    override = os.environ.get(env_name)
    if override:
        return Path(override).expanduser().resolve()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


# Packaged layout first (inside this folder), then the sibling layout used
# while developing.
MODEL_PATH = _locate(
    "MING_MODEL_PATH",
    ROOT / "models" / "Ming-3.0-tts-0.5B",
    ROOT.parent / "models" / "Ming-3.0-tts-0.5B",
)
VENDOR_PATH = _locate(
    "MING_REPO_PATH",
    ROOT / "vendor" / "Ming-3.0-tts",
    ROOT.parent / "vendor" / "Ming-3.0-tts",
)

VOICES = ["US_Emma", "UK_George", "UK_Charlotte"]

LEADING_SILENCE_THRESHOLD = 0.005
LEADING_PREROLL_SECONDS = 0.05
NO_STRETCH_BAND = 0.02


class TTSEngine:
    """Loads the model in the background and synthesizes one line at a time."""

    def __init__(self):
        self.state = "idle"  # idle | loading | ready | error
        self.error = None
        self.device = None
        self.sample_rate = 44100
        self._model = None
        self._normalize_numbers = None
        self._lock = threading.Lock()

    def start_loading(self):
        with self._lock:
            if self.state in ("loading", "ready"):
                return
            self.state, self.error = "loading", None
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            import torch

            if str(VENDOR_PATH) not in sys.path:
                sys.path.insert(0, str(VENDOR_PATH))
            from ming_tts import MingTTS

            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            # pynini (FST text normalization) is not installed, so numbers are
            # expanded with the repo's pure-Python English helper instead.
            self._model = MingTTS(
                str(MODEL_PATH), device=self.device, text_normalization=False)
            self.sample_rate = self._model.sample_rate
            try:
                from frontend.number_en import normalize_numbers
                self._normalize_numbers = normalize_numbers
            except Exception:
                self._normalize_numbers = None
            self.state = "ready"
        except Exception as error:  # surfaced in the UI
            self.state, self.error = "error", f"{type(error).__name__}: {error}"

    def synthesize(self, text, voice):
        """Return mono float32 samples at ``self.sample_rate``."""
        if self._normalize_numbers is not None:
            try:
                text = self._normalize_numbers(text)
            except Exception:
                pass
        waveform = self._model.synthesize(
            task="IP",
            text=text,
            language_id="en",
            controls={"ip": voice},
            use_zero_spk_emb=True,
        )
        samples = waveform.detach().float().cpu().numpy().reshape(-1)
        return np.ascontiguousarray(samples, dtype=np.float32)


# -- audio helpers ----------------------------------------------------------

@functools.lru_cache(maxsize=1)
def ffmpeg_exe():
    """Path of an ffmpeg executable, or None.

    ffmpeg is optional: it is used for time-stretching only when it is present
    (the imageio-ffmpeg wheel or one on PATH). Set MING_STRETCH=python to ignore
    it, e.g. where running external executables is not allowed.
    """
    if os.environ.get("MING_STRETCH", "auto").strip().lower() == "python":
        return None
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if Path(exe).is_file():
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


_ffmpeg_failed = False


def stretch_method():
    return "ffmpeg" if ffmpeg_exe() and not _ffmpeg_failed else "python"


def trim_leading_silence(samples, sample_rate):
    loud = np.flatnonzero(np.abs(samples) > LEADING_SILENCE_THRESHOLD)
    if loud.size == 0:
        return samples
    start = max(0, int(loud[0]) - int(LEADING_PREROLL_SECONDS * sample_rate))
    return samples[start:]


def tempo_ffmpeg(samples, sample_rate, tempo):
    command = [
        ffmpeg_exe(), "-hide_banner", "-loglevel", "error",
        "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
        "-filter:a", f"atempo={tempo:.5f}",
        "-f", "f32le", "-ar", str(sample_rate), "-ac", "1", "pipe:1",
    ]
    result = subprocess.run(
        command, input=samples.tobytes(), capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + result.stderr.decode(errors="replace"))
    return np.frombuffer(result.stdout, dtype=np.float32).copy()


def tempo_python(samples, sample_rate, tempo):
    """Pitch-preserving time-stretch with WSOLA (numpy only, no executables).

    Overlapping 25 ms Hann frames are read from the input at ``tempo`` times the
    output hop; each read position is nudged within +-12 ms to the point that best
    continues the previous frame, which keeps voiced speech free of phasing.
    """
    x = samples.astype(np.float64)
    frame = int(0.025 * sample_rate) // 2 * 2
    hop = frame // 2
    tol = int(0.012 * sample_rate)
    n_out = max(1, int(round(len(x) / tempo)))
    n_frames = -(-n_out // hop) + 1
    padded = np.pad(x, (tol, int(n_frames * hop * tempo) + frame + tol + hop))
    window = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(frame) / frame)
    out = np.zeros(n_frames * hop + frame)
    weight = np.zeros_like(out)

    previous = tol
    for k in range(n_frames):
        if k == 0:
            position = tol
        else:
            nominal = tol + int(round(k * hop * tempo))
            lo = nominal - tol
            segment = padded[lo:lo + 2 * tol + frame]
            target = padded[previous + hop:previous + hop + frame]
            correlation = np.correlate(segment, target, mode="valid")
            energy = np.concatenate(([0.0], np.cumsum(segment * segment)))
            energy = energy[frame:frame + 2 * tol + 1] - energy[:2 * tol + 1]
            position = lo + int(np.argmax(correlation / np.sqrt(energy + 1e-9)))
        start = k * hop
        out[start:start + frame] += padded[position:position + frame] * window
        weight[start:start + frame] += window
        previous = position
    out /= np.maximum(weight, 1e-3)
    return out[:n_out].astype(np.float32)


def change_tempo(samples, sample_rate, tempo):
    """Speed up (tempo > 1) or slow down (tempo < 1) without changing pitch.

    Uses ffmpeg when it is available, and the built-in stretcher otherwise or if
    running ffmpeg fails (blocked executable, bad build).
    """
    global _ffmpeg_failed
    if stretch_method() == "ffmpeg":
        try:
            return tempo_ffmpeg(samples, sample_rate, tempo)
        except (OSError, RuntimeError):
            _ffmpeg_failed = True
    return tempo_python(samples, sample_rate, tempo)


def fit_to_slot(samples, sample_rate, duration, min_tempo, max_tempo):
    """Fit ``samples`` into ``duration`` seconds.

    Returns ``(fitted, tempo, overrun_seconds)``. The tempo is clamped to
    [min_tempo, max_tempo]; if the clamp stops the audio reaching the slot
    length, shorter audio is padded with silence and longer audio is kept whole
    and reported as an overrun.
    """
    natural = len(samples) / sample_rate
    wanted = natural / duration  # tempo needed to land exactly on the slot
    tempo = min(max(wanted, min_tempo), max_tempo)
    if abs(tempo - 1.0) > NO_STRETCH_BAND:
        samples = change_tempo(samples, sample_rate, tempo)
    else:
        tempo = 1.0

    slot = int(round(duration * sample_rate))
    exact = abs(tempo - wanted) < 1e-3
    if len(samples) < slot:
        samples = np.pad(samples, (0, slot - len(samples)))
    elif exact:
        samples = samples[:slot]  # drop the few samples of ffmpeg rounding
    overrun = max(0.0, (len(samples) - slot) / sample_rate)
    return samples, tempo, overrun


def mix_timeline(clips, sample_rate):
    """Place each ``(start_seconds, samples)`` clip on one silent track."""
    if not clips:
        return np.zeros(0, dtype=np.float32)
    total = max(int(round(start * sample_rate)) + len(samples) for start, samples in clips)
    track = np.zeros(total, dtype=np.float32)
    for start, samples in clips:
        offset = int(round(start * sample_rate))
        track[offset:offset + len(samples)] += samples
    peak = float(np.max(np.abs(track))) if total else 0.0
    if peak > 1.0:
        track /= peak
    return track


def write_wav(path, samples, sample_rate):
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")


def write_zip(job_dir, names):
    archive = job_dir / "all_audio.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            bundle.write(job_dir / name, arcname=name)
    return archive.name


def write_manifest(job_dir, payload):
    (job_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
