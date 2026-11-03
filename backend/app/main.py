"""FastAPI service: cameras, MJPEG streams, rules/alerts, media, live stats over WebSocket."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import re
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, db, detector
from .camera import pick_device
from .config import BASE_DIR, EVAL_DIR, FACE_MODEL, MEDIA_DIR, POSE_WEIGHTS, SAMPLE_DIR, UPLOAD_DIR
from .manager import CameraManager, discover_webcams
from .ppe import available as ppe_available

manager = CameraManager()
MAX_UPLOAD_MB = 300
STARTED_AT = time.time()
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.restore()
    task = asyncio.create_task(broadcaster())
    yield
    task.cancel()
    manager.shutdown()


app = FastAPI(title="Vision Monitor API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

clients: set[WebSocket] = set()

# Rolling analytics history: one point every 5 s, kept for 1 hour (720 points).
history: "deque[dict]" = deque(maxlen=720)


# ------------------------------------------------------------------------ auth
OPEN_PATHS = {"/api/auth/login", "/api/auth/me", "/api/auth/logout", "/api/health"}


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if auth.ENABLED and path.startswith("/api/") and path not in OPEN_PATHS:
        who = auth.verify_token(request.cookies.get(auth.COOKIE))
        if who is None:
            return JSONResponse({"detail": "Login required"}, status_code=401)
        if request.method not in ("GET", "HEAD", "OPTIONS") and who[1] != "admin":
            return JSONResponse({"detail": "Read-only account: admin rights required"}, status_code=403)
    return await call_next(request)


class Login(BaseModel):
    username: str
    password: str


@app.get("/api/auth/me")
def auth_me(request: Request):
    if not auth.ENABLED:
        return {"required": False, "user": None, "role": "admin"}
    who = auth.verify_token(request.cookies.get(auth.COOKIE))
    return {"required": True, "user": who[0] if who else None, "role": who[1] if who else None}


@app.post("/api/auth/login")
def auth_login(body: Login, request: Request):
    if not auth.ENABLED:
        return {"required": False}
    ip = request.client.host if request.client else "?"
    if auth.too_many_attempts(ip):
        raise HTTPException(429, "Too many attempts, wait a minute")
    role = auth.check_login(ip, body.username, body.password)
    if role is None:
        raise HTTPException(401, "Invalid username or password")
    resp = JSONResponse({"required": True, "user": body.username, "role": role})
    resp.set_cookie(auth.COOKIE, auth.make_token(body.username, role), httponly=True, samesite="lax", max_age=auth.TTL)
    return resp


@app.post("/api/auth/logout")
def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE)
    return resp


# ------------------------------------------------------------------- websocket
async def broadcaster() -> None:
    """Push stats once per second and events as they happen."""
    last_stats = 0.0
    last_hist = 0.0
    while True:
        await asyncio.sleep(0.25)
        msgs = []
        while not manager.events.empty():
            msgs.append({"type": "event", "event": manager.events.get_nowait()})
        if time.time() - last_hist >= 5.0:
            last_hist = time.time()
            sm = manager.summary()
            if sm["cameras"]:
                history.append({"ts": last_hist, "live": sm["live"], "current": sm["current"],
                                "unique": sm["unique"], "fps": sm["avg_fps"], "latency_ms": sm["avg_latency_ms"]})
        if time.time() - last_stats >= 1.0:
            last_stats = time.time()
            msgs.append({"type": "stats", "cameras": manager.snapshot(), "summary": manager.summary(),
                         "alerts_unacked": db.unacked_alerts()})
        for m in msgs:
            for ws in list(clients):
                try:
                    await ws.send_json(m)
                except Exception:
                    clients.discard(ws)


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if auth.ENABLED and auth.verify_token(ws.cookies.get(auth.COOKIE)) is None:
        await ws.close(code=4401)
        return
    await ws.accept()
    clients.add(ws)
    await ws.send_json({"type": "stats", "cameras": manager.snapshot(), "summary": manager.summary(),
                        "alerts_unacked": db.unacked_alerts()})
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
    pose: bool | None = None
    ppe: bool | None = None
    model: str | None = None
    name: str | None = None
    zones: list[dict] | None = None
    lines: list[dict] | None = None


class Ack(BaseModel):
    id: int | None = None
    all: bool = False


class WebhookBody(BaseModel):
    url: str = ""


# ------------------------------------------------------------------------ REST
@app.get("/api/health")
def health():
    return {
        "ok": True, "device": pick_device(), "model": detector.current(),
        "face_model": FACE_MODEL.name if FACE_MODEL.exists() else None,
        "pose_model": POSE_WEIGHTS.name if POSE_WEIGHTS.exists() else None,
        "ppe_model": "ppe.pt" if ppe_available() else None,
        "tracker": "ByteTrack", "uptime": round(time.time() - STARTED_AT),
        "auth": auth.ENABLED,
    }


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
    except ValueError as e:
        raise HTTPException(400, str(e))


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
def snapshot(cam_id: str, raw: bool = False):
    try:
        w = manager.get(cam_id)
        jpg = w.raw_jpeg() if raw else w.latest_jpeg()
    except KeyError:
        raise HTTPException(404, "camera not found")
    if not jpg:
        raise HTTPException(404, "no frame yet")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/cameras/{cam_id}/heatmap")
def heatmap(cam_id: str):
    try:
        jpg = manager.get(cam_id).render_heatmap()
    except KeyError:
        raise HTTPException(404, "camera not found")
    if not jpg:
        raise HTTPException(404, "no frame yet")
    return Response(jpg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/cameras/{cam_id}/heatmap/reset")
def heatmap_reset(cam_id: str):
    try:
        manager.get(cam_id).reset_heatmap()
    except KeyError:
        raise HTTPException(404, "camera not found")
    return {"ok": True}


@app.get("/api/summary")
def summary():
    return manager.summary()


@app.get("/api/history")
def get_history(minutes: int = 30):
    cutoff = time.time() - min(max(minutes, 1), 60) * 60
    return [h for h in history if h["ts"] >= cutoff]


@app.get("/api/events")
def events(limit: int = 100, camera_id: str | None = None, severity: str | None = None):
    return db.list_events(min(limit, 1000), camera_id, severity)


@app.get("/api/alerts")
def alerts(limit: int = 100):
    return db.list_events(min(limit, 500), severity="alert")


@app.post("/api/alerts/ack")
def ack(body: Ack):
    if not body.all and body.id is None:
        raise HTTPException(400, "Provide id or all=true")
    return {"acknowledged": db.ack_alert(None if body.all else body.id)}


@app.get("/api/media/{name}")
def media(name: str):
    if not SAFE_NAME.match(name):
        raise HTTPException(400, "bad name")
    p = MEDIA_DIR / name
    if not p.is_file():
        raise HTTPException(404, "not found (a clip may still be processing)")
    return FileResponse(p, media_type="video/mp4" if name.endswith(".mp4") else "image/jpeg")


@app.get("/api/settings/webhook")
def get_webhook():
    url = db.get_kv("webhook_url")
    return {"configured": bool(url), "host": urlparse(url).netloc if url else None}


@app.put("/api/settings/webhook")
def put_webhook(body: WebhookBody):
    url = body.url.strip()
    if url and urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(400, "Webhook URL must start with http:// or https://")
    db.set_kv("webhook_url", url)
    return {"configured": bool(url), "host": urlparse(url).netloc if url else None}


@app.post("/api/settings/webhook/test")
def test_webhook():
    url = db.get_kv("webhook_url")
    if not url:
        raise HTTPException(400, "No webhook configured")
    manager._post_webhook(url, {"id": 0, "ts": time.time(), "camera_id": "test", "camera_name": "Vision Monitor",
                                "type": "test", "message": "Test alert from Vision Monitor", "severity": "alert"})
    return {"sent": True}


class DetectorBody(BaseModel):
    file: str


@app.get("/api/settings/detector")
def get_detector():
    return {"current": detector.current(), "options": detector.options()}


@app.put("/api/settings/detector")
def put_detector(body: DetectorBody):
    ok = {o["file"] for o in detector.options() if o["installed"]}
    if body.file not in ok:
        raise HTTPException(400, "Model not installed. Run backend/download_models.sh or choose another.")
    if body.file != detector.current():
        db.set_kv("detector", body.file)
        threading.Thread(target=manager.restart_all, daemon=True).start()   # cameras reload with the new weights
    return {"current": body.file, "options": detector.options()}


@app.get("/api/eval")
def eval_results():
    out = []
    for p in sorted(EVAL_DIR.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            continue
    return out


@app.get("/api/report.csv")
def report_csv():
    buf = io.StringIO()
    wr = csv.writer(buf)
    wr.writerow(["time", "camera", "event", "severity", "label", "track_id", "zone", "confidence", "message"])
    for e in reversed(db.list_events(5000)):
        wr.writerow([time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e["ts"])), e["camera_name"], e["type"],
                     e["severity"], e["label"], e["track_id"], e["zone"], e["confidence"], e["message"]])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=detection_report.csv"})


# Serve the built dashboard when present (Docker / production). Hash routing means no SPA fallback is needed.
_dist = BASE_DIR.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
