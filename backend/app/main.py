"""FastAPI service: camera management, MJPEG streams, live stats over WebSocket."""
from __future__ import annotations

import asyncio
import csv
import io
import re
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from . import db
from .camera import pick_device
from .config import SAMPLE_DIR, UPLOAD_DIR, YOLO_WEIGHTS
from .manager import CameraManager, discover_webcams

manager = CameraManager()
MAX_UPLOAD_MB = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.restore()
    task = asyncio.create_task(broadcaster())
    yield
    task.cancel()
    manager.shutdown()


app = FastAPI(title="AI Video Analytics Demo", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

clients: set[WebSocket] = set()


async def broadcaster() -> None:
    """Push stats once per second and events as they happen."""
    last_stats = 0.0
    while True:
        await asyncio.sleep(0.25)
        msgs = []
        while not manager.events.empty():
            msgs.append({"type": "event", "event": manager.events.get_nowait()})
        if time.time() - last_stats >= 1.0:
            last_stats = time.time()
            msgs.append({"type": "stats", "cameras": manager.snapshot(), "summary": manager.summary()})
        for m in msgs:
            for ws in list(clients):
                try:
                    await ws.send_json(m)
                except Exception:
                    clients.discard(ws)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json({"type": "stats", "cameras": manager.snapshot(), "summary": manager.summary()})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients.discard(ws)


# ---------------------------------------------------------------------- models
class NewCamera(BaseModel):
    name: str = ""
    kind: str          # webcam | file | rtsp
    source: str        # webcam index | filename in uploads/samples | rtsp url
    faces: bool = True


class SettingsPatch(BaseModel):
    conf: float | None = None
    faces: bool | None = None
    tracking: bool | None = None
    name: str | None = None


# ------------------------------------------------------------------------ REST
@app.get("/api/health")
def health():
    return {"ok": True, "device": pick_device(), "model": YOLO_WEIGHTS.name}


@app.get("/api/cameras")
def list_cameras():
    return manager.snapshot()


@app.post("/api/cameras")
def add_camera(body: NewCamera):
    try:
        w = manager.add(body.name, body.kind, body.source, {"faces": body.faces})
    except ValueError as e:
        raise HTTPException(400, str(e))
    return w.snapshot()


@app.post("/api/cameras/upload")
async def upload_camera(file: UploadFile = File(...), name: str = Form("")):
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in {"mp4", "mov", "avi", "mkv", "webm", "m4v"}:
        raise HTTPException(400, "Upload an mp4, mov, avi, mkv or webm video")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename or "video." + ext)
    dest = UPLOAD_DIR / f"{int(time.time())}_{safe}"
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Video larger than {MAX_UPLOAD_MB} MB")
            f.write(chunk)
    w = manager.add(name or safe.rsplit(".", 1)[0], "file", dest.name)
    return w.snapshot()


@app.get("/api/discover")
def discover():
    in_use = {int(m["source"]) for m in manager.meta.values() if m["kind"] == "webcam"}
    return discover_webcams(skip=in_use)


@app.get("/api/samples")
def samples():
    return [{"file": p.name, "name": p.stem.replace("-", " ").title()} for p in sorted(SAMPLE_DIR.glob("*.mp4"))]


@app.delete("/api/cameras/{cam_id}")
def remove_camera(cam_id: str):
    manager.remove(cam_id)
    return {"ok": True}


@app.post("/api/cameras/{cam_id}/start")
def start_camera(cam_id: str):
    try:
        return manager.start(cam_id).snapshot()
    except KeyError:
        raise HTTPException(404, "camera not found")


@app.post("/api/cameras/{cam_id}/stop")
def stop_camera(cam_id: str):
    try:
        manager.stop(cam_id)
    except KeyError:
        raise HTTPException(404, "camera not found")
    return {"ok": True}


@app.patch("/api/cameras/{cam_id}")
def patch_camera(cam_id: str, body: SettingsPatch):
    try:
        return manager.update_settings(cam_id, body.model_dump(exclude_none=True))
    except KeyError:
        raise HTTPException(404, "camera not found")


@app.get("/api/cameras/{cam_id}/stream")
async def stream(cam_id: str):
    try:
        w = manager.get(cam_id)
    except KeyError:
        raise HTTPException(404, "camera not found")

    async def gen():
        seq = 0
        loop = asyncio.get_running_loop()
        while True:
            seq, jpg = await loop.run_in_executor(None, w.wait_frame, seq, 5.0)
            if w.status in ("stopped", "error") and not w.is_alive():
                break
            if jpg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/cameras/{cam_id}/snapshot")
def snapshot(cam_id: str):
    try:
        jpg = manager.get(cam_id).latest_jpeg()
    except KeyError:
        raise HTTPException(404, "camera not found")
    if not jpg:
        raise HTTPException(404, "no frame yet")
    return Response(jpg, media_type="image/jpeg")


@app.get("/api/summary")
def summary():
    return manager.summary()


@app.get("/api/events")
def events(limit: int = 100, camera_id: str | None = None):
    return db.list_events(min(limit, 1000), camera_id)


@app.get("/api/report.csv")
def report_csv():
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["time", "camera", "event", "label", "track_id", "confidence", "message"])
    for e in reversed(db.list_events(5000)):
        wr.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["ts"])), e["camera_name"], e["type"],
                     e["label"], e["track_id"], e["confidence"], e["message"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=detection_report.csv"})
