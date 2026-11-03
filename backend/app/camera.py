"""One worker thread per camera: capture -> YOLO + ByteTrack -> faces -> overlay -> JPEG."""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Callable

import cv2
import numpy as np

from .config import (
    CATEGORIES, CATEGORY_COLORS, COCO_CLASSES, DETECT_CLASS_IDS, FACE_MODEL,
    JPEG_QUALITY, STREAM_MAX_WIDTH, UNCERTAIN_BELOW, YOLO_WEIGHTS,
)

# Inference is serialised: several camera threads share one accelerator (Apple MPS / CUDA / CPU).
_INFER_LOCK = threading.Lock()
_DEVICE: str | None = None


def pick_device() -> str:
    global _DEVICE
    if _DEVICE is None:
        try:
            import torch
            if torch.cuda.is_available():
                _DEVICE = "cuda:0"
            elif torch.backends.mps.is_available():
                _DEVICE = "mps"
            else:
                _DEVICE = "cpu"
        except Exception:
            _DEVICE = "cpu"
    return _DEVICE


DEFAULT_SETTINGS = {"conf": 0.35, "faces": True, "tracking": True}


class CameraWorker(threading.Thread):
    def __init__(
        self,
        cam_id: str,
        name: str,
        kind: str,           # webcam | file | rtsp
        source: str,         # webcam index / absolute file path / rtsp url
        settings: dict | None,
        on_event: Callable[[dict], None],
    ) -> None:
        super().__init__(daemon=True, name=f"cam-{cam_id}")
        self.cam_id, self.name_, self.kind, self.source = cam_id, name, kind, source
        self.settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self.on_event = on_event

        self._stop_evt = threading.Event()
        self._frame_cv = threading.Condition()
        self._jpeg: bytes | None = None
        self._frame_seq = 0

        self.status = "starting"   # starting | live | error | stopped
        self.error: str | None = None
        self.fps = 0.0
        self.latency_ms = 0.0
        self.resolution = ""
        self.started_at = time.time()
        self.loops = 0

        self.current: dict[str, int] = {c: 0 for c in CATEGORIES}
        self.current["face"] = 0
        self._unique: dict[str, set[int]] = defaultdict(set)
        self.detections_total = 0   # frame-by-frame detections (NOT unique people)
        self.frames = 0

        self._model = None
        self._face = None

    # ------------------------------------------------------------------ public
    def stop(self) -> None:
        self._stop_evt.set()

    def snapshot(self) -> dict:
        return {
            "id": self.cam_id,
            "name": self.name_,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "fps": round(self.fps, 1),
            "latency_ms": round(self.latency_ms, 1),
            "resolution": self.resolution,
            "settings": self.settings,
            "current": dict(self.current),
            "unique": {c: len(self._unique.get(c, ())) for c in CATEGORIES},
            "detections_total": self.detections_total,
            "frames": self.frames,
            "uptime": round(time.time() - self.started_at, 0),
            "loops": self.loops,
            "device": pick_device(),
        }

    def wait_frame(self, last_seq: int, timeout: float = 5.0) -> tuple[int, bytes | None]:
        with self._frame_cv:
            self._frame_cv.wait_for(lambda: self._frame_seq != last_seq or self._stop_evt.is_set(), timeout)
            return self._frame_seq, self._jpeg

    def latest_jpeg(self) -> bytes | None:
        return self._jpeg

    # ----------------------------------------------------------------- helpers
    def _emit(self, **kw) -> None:
        self.on_event({"ts": time.time(), "camera_id": self.cam_id, "camera_name": self.name_, **kw})

    def _open(self) -> cv2.VideoCapture:
        if self.kind == "webcam":
            cap = cv2.VideoCapture(int(self.source))
        else:
            cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            raise RuntimeError(
                "Could not open webcam (check camera permission for your terminal)"
                if self.kind == "webcam" else f"Could not open source: {self.source}"
            )
        return cap

    def _load_models(self) -> None:
        from ultralytics import YOLO
        self._model = YOLO(str(YOLO_WEIGHTS))
        if FACE_MODEL.exists() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._face = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), 0.7, 0.3, 200)
            except Exception:
                self._face = None

    def _reset_tracker(self) -> None:
        try:
            for t in self._model.predictor.trackers:
                t.reset()
        except Exception:
            pass
        self._unique.clear()
        self.current = {k: 0 for k in self.current}

    # --------------------------------------------------------------- main loop
    def run(self) -> None:
        cap = None
        try:
            self._load_models()
            cap = self._open()
            src_fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frame_dt = 1.0 / src_fps if (self.kind == "file" and 1 < src_fps < 120) else 0.0
            self.status = "live"
            self._emit(type="camera_online", message=f"{self.name_} is live")
            ema_fps, t_prev = 0.0, time.time()
            fail = 0

            while not self._stop_evt.is_set():
                t_frame = time.time()
                ok, frame = cap.read()
                if not ok:
                    if self.kind == "file":      # loop uploaded / sample videos
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        self.loops += 1
                        self._reset_tracker()
                        continue
                    fail += 1
                    if fail > 30:
                        raise RuntimeError("Stream lost (no frames received)")
                    time.sleep(0.05)
                    continue
                fail = 0

                # downscale for speed / bandwidth
                h, w = frame.shape[:2]
                if w > STREAM_MAX_WIDTH:
                    s = STREAM_MAX_WIDTH / w
                    frame = cv2.resize(frame, (STREAM_MAX_WIDTH, int(h * s)), interpolation=cv2.INTER_AREA)
                    h, w = frame.shape[:2]
                self.resolution = f"{w}x{h}"

                t0 = time.time()
                dets = self._detect(frame)
                faces = self._faces(frame) if self.settings.get("faces") else []
                self.latency_ms = 0.8 * self.latency_ms + 0.2 * ((time.time() - t0) * 1000) if self.latency_ms else (time.time() - t0) * 1000

                self._update_stats(dets, faces)
                self._draw(frame, dets, faces)
                ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok2:
                    with self._frame_cv:
                        self._jpeg = buf.tobytes()
                        self._frame_seq += 1
                        self._frame_cv.notify_all()

                self.frames += 1
                now = time.time()
                inst = 1.0 / max(now - t_prev, 1e-3)
                ema_fps = inst if ema_fps == 0 else 0.9 * ema_fps + 0.1 * inst
                self.fps = ema_fps
                t_prev = now

                if frame_dt:  # real-time pacing for video files
                    sleep = frame_dt - (time.time() - t_frame)
                    if sleep > 0:
                        time.sleep(sleep)
            self.status = "stopped"
        except Exception as e:  # noqa: BLE001 - surface any failure to the dashboard
            self.status = "error"
            self.error = str(e)
            self._emit(type="camera_error", message=f"{self.name_}: {e}")
        finally:
            if cap is not None:
                cap.release()
            if self.status == "live":
                self.status = "stopped"
            if self.status == "stopped":
                self._emit(type="camera_offline", message=f"{self.name_} stopped")
            with self._frame_cv:
                self._frame_cv.notify_all()

    # --------------------------------------------------------------- inference
    def _detect(self, frame: np.ndarray) -> list[dict]:
        kwargs = dict(
            conf=float(self.settings.get("conf", 0.35)),
            classes=DETECT_CLASS_IDS,
            imgsz=640,
            verbose=False,
            device=pick_device(),
        )
        with _INFER_LOCK:
            if self.settings.get("tracking", True):
                res = self._model.track(frame, persist=True, tracker="bytetrack.yaml", **kwargs)[0]
            else:
                res = self._model.predict(frame, **kwargs)[0]
        out: list[dict] = []
        boxes = res.boxes
        if boxes is None or len(boxes) == 0:
            return out
        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [None] * len(clss)
        for b, c, k, tid in zip(xyxy, confs, clss, ids):
            if int(k) not in COCO_CLASSES:
                continue
            label, cat = COCO_CLASSES[int(k)]
            out.append({"box": b, "conf": float(c), "label": label, "cat": cat,
                        "id": int(tid) if tid is not None else None})
        return out

    def _faces(self, frame: np.ndarray) -> list[dict]:
        if self._face is None:
            return []
        h, w = frame.shape[:2]
        self._face.setInputSize((w, h))
        with _INFER_LOCK:
            _, faces = self._face.detect(frame)
        out = []
        if faces is not None:
            for f in faces:
                x, y, fw, fh = f[:4]
                out.append({"box": np.array([x, y, x + fw, y + fh]), "conf": float(f[-1]),
                            "lm": f[4:14].reshape(5, 2)})
        return out

    # ------------------------------------------------------------- bookkeeping
    def _update_stats(self, dets: list[dict], faces: list[dict]) -> None:
        cur = {c: 0 for c in CATEGORIES}
        for d in dets:
            cur[d["cat"]] += 1
            self.detections_total += 1
            tid = d["id"]
            if tid is not None and tid not in self._unique[d["cat"]]:
                self._unique[d["cat"]].add(tid)
                self._emit(type="new_track", label=d["label"], track_id=tid, confidence=round(d["conf"], 2),
                           message=f"New {d['label']} #{tid}")
        cur["face"] = len(faces)
        self.current = cur

    # ----------------------------------------------------------------- overlay
    def _draw(self, frame: np.ndarray, dets: list[dict], faces: list[dict]) -> None:
        for d in dets:
            x1, y1, x2, y2 = d["box"].astype(int)
            col = CATEGORY_COLORS.get(d["cat"], (200, 200, 200))
            uncertain = d["conf"] < UNCERTAIN_BELOW
            thick = 1 if uncertain else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), col, thick)
            tag = f"{d['label']}{'?' if uncertain else ''}"
            if d["id"] is not None:
                tag += f" #{d['id']}"
            tag += f" {d['conf']:.2f}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            ty = max(y1, th + 6)
            cv2.rectangle(frame, (x1, ty - th - 6), (x1 + tw + 6, ty), col, -1)
            cv2.putText(frame, tag, (x1 + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 10, 10), 1, cv2.LINE_AA)
        for f in faces:
            x1, y1, x2, y2 = f["box"].astype(int)
            col = CATEGORY_COLORS["face"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), col, 1)
            for (lx, ly) in f["lm"].astype(int):
                cv2.circle(frame, (lx, ly), 2, (0, 200, 255), -1)
            cv2.putText(frame, f"face {f['conf']:.2f}", (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)
        # HUD
        hud = f"{self.name_}  {self.fps:.1f} FPS  {self.latency_ms:.0f} ms"
        cv2.putText(frame, hud, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(frame, hud, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
