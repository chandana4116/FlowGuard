import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import config
import db
from processor import Processor

db.init()
proc = Processor()


@asynccontextmanager
async def lifespan(app):
    proc.start()
    videos = sorted(config.VIDEOS.glob("*.mp4"))        # auto-play the first video found
    if videos:
        proc.set_source(str(videos[0]))
    yield


app = FastAPI(title="FlowGuard API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/evidence", StaticFiles(directory=config.EVIDENCE), name="evidence")


@app.get("/api/status")
def status():
    return {**proc.status, "stats": proc.engine.stats, "tuning": proc.engine.tuning}


@app.get("/api/stream")
def stream():
    def frames():
        while True:
            jpg = proc.get_frame()
            if jpg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.05)
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/incidents")
def incidents(status: str | None = None):
    return db.list_incidents(status)


@app.post("/api/incidents/{iid}/acknowledge")
def acknowledge(iid: int):
    if not db.get(iid):
        raise HTTPException(404, "incident not found")
    db.set_status(iid, "ACKNOWLEDGED")
    proc.engine.acknowledge(iid)
    return db.get(iid)


@app.post("/api/incidents/{iid}/false-positive")
def false_positive(iid: int):
    row = db.get(iid)
    if not row:
        raise HTTPException(404, "incident not found")
    db.set_status(iid, "FALSE_POSITIVE")
    proc.engine.false_positive(row)          # tunes thresholds for this camera
    return db.get(iid)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    original_name = Path(file.filename or "traffic.mp4").name
    if Path(original_name).suffix.lower() != ".mp4":
        raise HTTPException(400, "Please upload an MP4 video.")
    # Always use a new filename. Replacing a file currently being read by
    # OpenCV can leave VideoCapture displaying the previous file.
    dest = config.VIDEOS / f"{Path(original_name).stem}_{uuid.uuid4().hex[:8]}.mp4"
    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except OSError as exc:
        raise HTTPException(500, f"Could not save uploaded video: {exc}") from exc
    db.clear_all()
    proc.set_source(str(dest))               # switch source and learn a fresh baseline
    return {"source": dest.name, "message": "Video uploaded; switching source and recalibrating."}
