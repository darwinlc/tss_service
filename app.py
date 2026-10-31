"""Web portal: upload a cue file (timing, duration, text) and generate speech."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import engine
from cues import MAX_CUES, MAX_TEXT_CHARS, CueError, parse_cues

OUTPUT_DIR = engine.ROOT / "outputs"
STATIC_DIR = engine.ROOT / "static"
OUTPUT_DIR.mkdir(exist_ok=True)

OVERRUN_TOLERANCE = 0.05  # seconds a line may exceed its slot before it is flagged

app = FastAPI(title="Ming TTS cue portal")
tts = engine.TTSEngine()
worker = ThreadPoolExecutor(max_workers=1)  # one GPU job at a time
jobs = {}
jobs_lock = threading.Lock()


class CueIn(BaseModel):
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class JobRequest(BaseModel):
    cues: list[CueIn] = Field(min_length=1, max_length=MAX_CUES)
    voice: Literal["US_Emma", "UK_George", "UK_Charlotte"] = "US_Emma"
    max_tempo: float = Field(default=1.3, ge=1.0, le=2.0)
    min_tempo: float = Field(default=0.9, ge=0.5, le=1.0)


@app.on_event("startup")
def startup():
    tts.start_loading()


@app.get("/api/status")
def status():
    return {
        "model": tts.state,
        "error": tts.error,
        "device": tts.device,
        "stretch": engine.stretch_method(),
        "voices": engine.VOICES,
        "max_cues": MAX_CUES,
    }


@app.post("/api/parse")
async def parse(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > 1_000_000:
        return JSONResponse({"errors": ["File is larger than 1 MB."]}, status_code=400)
    try:
        cues = parse_cues(raw)
    except CueError as error:
        return JSONResponse({"errors": error.errors}, status_code=400)
    return {"cues": cues}


@app.post("/api/jobs")
def create_job(request: JobRequest):
    if tts.state != "ready":
        raise HTTPException(409, "The model is not ready yet.")
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "state": "queued",  # queued | running | done | cancelled | error
        "error": None,
        "cancel": False,
        "settings": request.model_dump(exclude={"cues"}),
        "lines": [
            {
                "index": i,
                "start": cue.start,
                "duration": cue.duration,
                "text": cue.text,
                "state": "pending",  # pending | running | done | error | skipped
                "natural": None,
                "tempo": None,
                "final": None,
                "overrun": 0.0,
                "flag": None,
                "message": None,
                "file": None,
            }
            for i, cue in enumerate(request.cues, start=1)
        ],
        "timeline": None,
        "zip": None,
        "manifest": None,
    }
    with jobs_lock:
        jobs[job_id] = job
    worker.submit(run_job, job)
    return {"id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")
    return {key: value for key, value in job.items() if key != "cancel"}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job.")
    job["cancel"] = True
    return {"ok": True}


def run_job(job):
    job_dir = OUTPUT_DIR / job["id"]
    job_dir.mkdir(parents=True, exist_ok=True)
    settings = job["settings"]
    rate = tts.sample_rate
    job["state"] = "running"
    clips, written = [], []
    try:
        for line in job["lines"]:
            if job["cancel"]:
                line["state"] = "skipped"
                continue
            line["state"] = "running"
            try:
                samples = engine.trim_leading_silence(
                    tts.synthesize(line["text"], settings["voice"]), rate)
                line["natural"] = round(len(samples) / rate, 3)
                fitted, tempo, overrun = engine.fit_to_slot(
                    samples, rate, line["duration"],
                    settings["min_tempo"], settings["max_tempo"])
                name = f"line_{line['index']:03d}.wav"
                engine.write_wav(job_dir / name, fitted, rate)
                line.update(
                    tempo=round(tempo, 3),
                    final=round(len(fitted) / rate, 3),
                    overrun=round(overrun, 3),
                    file=f"/files/{job['id']}/{name}",
                    state="done",
                )
                if overrun > OVERRUN_TOLERANCE:
                    line["flag"] = "too_long"
                    line["message"] = (
                        f"{overrun:.2f}s over the slot even at {tempo:.2f}x; "
                        "shorten the text or lengthen the duration.")
                elif tempo == settings["min_tempo"] and tempo != 1.0:
                    line["flag"] = "padded"
                    line["message"] = "Shorter than the slot; padded with silence."
                clips.append((line["start"], fitted))
                written.append(name)
            except Exception as error:
                line["state"] = "error"
                line["message"] = f"{type(error).__name__}: {error}"

        if clips:
            timeline = engine.mix_timeline(clips, rate)
            engine.write_wav(job_dir / "timeline.wav", timeline, rate)
            written.insert(0, "timeline.wav")
            job["timeline"] = f"/files/{job['id']}/timeline.wav"
            engine.write_manifest(job_dir, {
                "sample_rate": rate,
                "voice": settings["voice"],
                "stretch_method": engine.stretch_method(),
                "timeline": "timeline.wav",
                "lines": [
                    {
                        "index": ln["index"], "start": ln["start"],
                        "duration": ln["duration"], "text": ln["text"],
                        "file": f"line_{ln['index']:03d}.wav" if ln["file"] else None,
                        "natural_seconds": ln["natural"], "tempo": ln["tempo"],
                        "final_seconds": ln["final"], "flag": ln["flag"],
                    }
                    for ln in job["lines"]
                ],
            })
            written.append("manifest.json")
            job["manifest"] = f"/files/{job['id']}/manifest.json"
            job["zip"] = f"/files/{job['id']}/{engine.write_zip(job_dir, written)}"
        job["state"] = "cancelled" if job["cancel"] else "done"
    except Exception as error:
        job["state"] = "error"
        job["error"] = f"{type(error).__name__}: {error}"


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")
