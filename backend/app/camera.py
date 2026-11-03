"""One worker thread per camera: capture -> YOLO + ByteTrack -> faces/pose/PPE -> rules -> overlay -> JPEG."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

import cv2
import numpy as np

from . import detector
from . import ppe as ppe_mod
from .config import (
    CATEGORIES, CATEGORY_COLORS, COCO_CLASSES, DETECT_CLASS_IDS, FACE_MODEL, JPEG_QUALITY,
    MODEL_DIR, OBJECT_MIN_CONF, POSE_WEIGHTS, PPE_MODEL, STREAM_MAX_WIDTH, UNCERTAIN_BELOW,
)
from .media import ClipRecorder
from . import atmosphere as atmo_mod
from .pose import SKELETON, classify_posture, iou
from .rules import RuleEngine, point_in_polygon

# Inference is serialised: several camera threads share one accelerator (Apple MPS / CUDA / CPU).
_INFER_LOCK = threading.Lock()
_DEVICE: str | None = None

HEAT_W, HEAT_H = 96, 54
FALL_AFTER_S = 1.5
POSTURES = ["standing", "sitting", "bending", "lying"]
NO_PPE = {"helmet_yes": 0, "helmet_no": 0, "helmet_unknown": 0}


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


DEFAULT_SETTINGS = {
    "conf": 0.25, "faces": True, "tracking": True, "pose": False, "ppe": False, "atmosphere": False, "zones": [], "lines": [],
    "model": "",   # "" = use the global detector (System page); otherwise a weights file such as yolo11x.pt
}


def hex_to_bgr(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) != 6:
        return (200, 200, 200)
    try:
        return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)
    except ValueError:
        return (200, 200, 200)


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
        self._raw: np.ndarray | None = None   # last frame without overlays (used by the zone editor)
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
        self._model_file = ""
        self._face = None
        self._pose = None
        self._ppe = None
        self.pose_error: str | None = None
        self.ppe_error: str | None = None

        self.recorder = ClipRecorder(cam_id)
        self.engine = RuleEngine(self._emit)
        self.apply_rules()
        self.heat = np.zeros((HEAT_H, HEAT_W), np.float32)
        self.postures: dict[str, int] = {p: 0 for p in POSTURES}
        self.ppe_counts: dict[str, int] = dict(NO_PPE)
        self._lying_since: dict[int, float] = {}
        self._fall_alerted: dict[int, float] = {}
        self._ppe_alerted: dict[tuple, float] = {}
        self._last_pose: list[dict] = []
        self._last_ppe: list[dict] = []
        self._frame_no = 0
        self.atmos: dict | None = None
        self._atmos_hist: deque = deque(maxlen=300)
        self._atmos_t = 0.0
        self._atmos_ema: float | None = None
        self._atmos_state = ("clear", "none")       # confirmed (level, kind)
        self._atmos_pending: tuple[tuple[str, str], int] = (("clear", "none"), 0)

    # ------------------------------------------------------------------ public
    def stop(self) -> None:
        self._stop_evt.set()

    def apply_rules(self) -> None:
        self.engine.configure(self.settings.get("zones", []), self.settings.get("lines", []))

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
            "model": self._model_file,
            "rules": self.engine.snapshot(),
            "postures": dict(self.postures),
            "ppe": dict(self.ppe_counts),
            "atmosphere": self.atmos if self.settings.get("atmosphere") else None,
            "features": {
                "pose_available": POSE_WEIGHTS.exists(), "pose_error": self.pose_error,
                "ppe_available": ppe_mod.available(), "ppe_error": self.ppe_error,
            },
        }

    def atmosphere_history(self) -> list[dict]:
        return list(self._atmos_hist)

    def wait_frame(self, last_seq: int, timeout: float = 5.0) -> tuple[int, bytes | None]:
        with self._frame_cv:
            self._frame_cv.wait_for(lambda: self._frame_seq != last_seq or self._stop_evt.is_set(), timeout)
            return self._frame_seq, self._jpeg

    def latest_jpeg(self) -> bytes | None:
        return self._jpeg

    def raw_jpeg(self) -> bytes | None:
        if self._raw is None:
            return None
        ok, buf = cv2.imencode(".jpg", self._raw, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes() if ok else None

    def reset_heatmap(self) -> None:
        self.heat[:] = 0

    def render_heatmap(self) -> bytes | None:
        base = self._jpeg
        if not base:
            return None
        img = cv2.imdecode(np.frombuffer(base, np.uint8), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        heat = cv2.GaussianBlur(self.heat, (0, 0), 1.6)
        if heat.max() <= 0:
            return base
        heat = np.sqrt(heat / heat.max())                     # sqrt lifts faint paths
        heat = cv2.resize(heat, (w, h), interpolation=cv2.INTER_CUBIC)
        colour = cv2.applyColorMap((np.clip(heat, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
        alpha = np.clip(heat * 1.4, 0, 0.75)[..., None]
        dark = (img * 0.55).astype(np.float32)
        out = (dark * (1 - alpha) + colour.astype(np.float32) * alpha).astype(np.uint8)
        ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else base

    # ----------------------------------------------------------------- helpers
    def _emit(self, **kw) -> None:
        capture = kw.pop("capture", False)
        ev = {"ts": time.time(), "camera_id": self.cam_id, "camera_name": self.name_, **kw}
        if capture:
            ev["image"], ev["clip"] = self.recorder.trigger(ev["ts"])
        self.on_event(ev)

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

    def _wanted_model(self) -> str:
        return self.settings.get("model") or detector.current()

    def _load_detector(self) -> None:
        from ultralytics import YOLO
        self._model_file = self._wanted_model()
        self._model = YOLO(str(MODEL_DIR / self._model_file))
        self._unique.clear()      # track IDs from the previous model are meaningless to the new tracker
        self.engine.reset()

    def _load_models(self) -> None:
        self._load_detector()
        if FACE_MODEL.exists() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._face = cv2.FaceDetectorYN.create(str(FACE_MODEL), "", (320, 320), 0.7, 0.3, 200)
            except Exception:
                self._face = None

    def _ensure_optional(self) -> None:
        """Load pose / PPE models lazily the first time they are switched on."""
        from ultralytics import YOLO
        if self.settings.get("pose") and self._pose is None and self.pose_error is None:
            try:
                self._pose = YOLO(str(POSE_WEIGHTS))
            except Exception as e:  # noqa: BLE001
                self.pose_error = f"Pose model unavailable: {e}"
        if self.settings.get("ppe") and self._ppe is None and self.ppe_error is None:
            if not ppe_mod.available():
                self.ppe_error = "No PPE model installed (backend/models/ppe.pt)"
            else:
                try:
                    self._ppe = YOLO(str(PPE_MODEL))
                except Exception as e:  # noqa: BLE001
                    self.ppe_error = f"PPE model failed to load: {e}"

    def _reset_tracker(self) -> None:
        try:
            for t in self._model.predictor.trackers:
                t.reset()
        except Exception:
            pass
        self._unique.clear()
        self.current = {k: 0 for k in self.current}
        self.engine.reset()
        self._lying_since.clear()

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
                self._frame_no += 1

                t0 = time.time()
                if self._wanted_model() != self._model_file:   # model changed from the dashboard
                    self._load_detector()
                self._ensure_optional()
                dets = self._detect(frame)
                faces = self._faces(frame) if self.settings.get("faces") else []
                if self._pose is not None and self.settings.get("pose"):
                    self._run_pose(frame, dets)
                else:
                    self.postures, self._last_pose = {p: 0 for p in POSTURES}, []
                if self._ppe is not None and self.settings.get("ppe"):
                    self._run_ppe(frame, dets, w, h)
                else:
                    self.ppe_counts, self._last_ppe = dict(NO_PPE), []
                self._run_atmosphere(frame)
                lat = (time.time() - t0) * 1000
                self.latency_ms = 0.8 * self.latency_ms + 0.2 * lat if self.latency_ms else lat

                self._raw = frame.copy()
                self.engine.update(dets, w, h)
                self._update_stats(dets, faces, w, h)
                self._draw(frame, dets, faces, w, h)
                ok2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                if ok2:
                    jpg = buf.tobytes()
                    self.recorder.push(time.time(), jpg)
                    with self._frame_cv:
                        self._jpeg = jpg
                        self._frame_seq += 1
                        self._frame_cv.notify_all()

                self.frames += 1
                now = time.time()
                inst = 1.0 / max(now - t_prev, 1e-3)
                ema_fps = inst if ema_fps == 0 else 0.9 * ema_fps + 0.1 * inst
                self.fps = ema_fps
                t_prev = now

                if frame_dt:  # keep video files at real-time speed: sleep if ahead, drop frames if behind
                    behind = time.time() - t_frame
                    if behind < frame_dt:
                        time.sleep(frame_dt - behind)
                    else:
                        for _ in range(min(int(behind / frame_dt), 12)):
                            if not cap.grab():
                                break
            self.status = "stopped"
        except Exception as e:  # noqa: BLE001 - surface any failure to the dashboard
            self.status = "error"
            self.error = str(e)
            self._emit(type="camera_error", severity="alert", message=f"{self.name_}: {e}")
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
            if cat == "object" and float(c) < OBJECT_MIN_CONF:
                continue
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

    def _run_pose(self, frame: np.ndarray, dets: list[dict]) -> None:
        """Pose runs on odd frames (result reused on even ones); posture is matched to tracked people."""
        if self._frame_no % 2 == 1:
            with _INFER_LOCK:
                res = self._pose.predict(frame, conf=0.4, imgsz=640, verbose=False, device=pick_device())[0]
            poses = []
            if res.keypoints is not None and res.boxes is not None and len(res.boxes):
                for box, kp in zip(res.boxes.xyxy.cpu().numpy(), res.keypoints.data.cpu().numpy()):
                    poses.append({"box": box, "kp": kp, "posture": classify_posture(kp)})
            self._last_pose = poses
        persons = [d for d in dets if d["cat"] == "person"]
        counts = {p: 0 for p in POSTURES}
        now = time.time()
        lying_ids = set()
        for pz in self._last_pose:
            best, best_i = None, 0.35
            for d in persons:
                v = iou(pz["box"], d["box"])
                if v > best_i:
                    best, best_i = d, v
            if best is None:
                continue
            best["posture"] = pz["posture"]
            if pz["posture"] in counts:
                counts[pz["posture"]] += 1
            tid = best["id"]
            if pz["posture"] == "lying" and tid is not None:
                lying_ids.add(tid)
                since = self._lying_since.setdefault(tid, now)
                if now - since >= FALL_AFTER_S and now - self._fall_alerted.get(tid, 0) > 30:
                    self._fall_alerted[tid] = now
                    self._emit(type="fall", label="person", track_id=tid, severity="alert", capture=True,
                               message=f"Possible fall: person #{tid} lying for over {FALL_AFTER_S:.1f}s — needs human review")
        for tid in [t for t in self._lying_since if t not in lying_ids]:
            del self._lying_since[tid]
        self.postures = counts

    def _run_atmosphere(self, frame: np.ndarray) -> None:
        """Fog / haze / smog estimate every ~2 s; alert only after 3 consistent readings (no flicker)."""
        if not self.settings.get("atmosphere"):
            self.atmos = None
            return
        now = time.time()
        if now - self._atmos_t < 2.0:
            return
        self._atmos_t = now
        r = atmo_mod.analyze(frame)
        if r["visibility"] is not None:   # smooth the score; "night" readings are reported but not smoothed
            self._atmos_ema = r["visibility"] if self._atmos_ema is None else 0.6 * self._atmos_ema + 0.4 * r["visibility"]
            r["visibility"] = round(self._atmos_ema, 1)
            r["level"] = atmo_mod.level_for(self._atmos_ema)
            if r["level"] == "clear":
                r["kind"] = "none"
        self.atmos = r
        self._atmos_hist.append({"ts": now, "visibility": r["visibility"], "level": r["level"], "kind": r["kind"]})
        if r["level"] == "night":
            return

        state = (r["level"], r["kind"])
        if state == self._atmos_pending[0]:
            self._atmos_pending = (state, self._atmos_pending[1] + 1)
        else:
            self._atmos_pending = (state, 1)
        if self._atmos_pending[1] < 3 or state == self._atmos_state:
            return
        prev, self._atmos_state = self._atmos_state, state
        level, kind = state
        what = "smog / possible pollution" if kind == "smog" else "fog"
        if level == "clear":
            if prev[0] != "clear":
                self._emit(type="visibility_clear", label="visibility", message=f"{self.name_}: visibility back to clear")
        elif level in ("foggy", "dense"):
            self._emit(type="visibility", label="visibility", severity="alert", capture=True,
                       confidence=round(r["visibility"] / 100, 2),
                       message=f"{self.name_}: {level} {what}, visibility index {r['visibility']:.0f}/100")
        else:
            self._emit(type="visibility", label="visibility", confidence=round(r["visibility"] / 100, 2),
                       message=f"{self.name_}: hazy {what}, visibility index {r['visibility']:.0f}/100")

    def _run_ppe(self, frame: np.ndarray, dets: list[dict], w: int, h: int) -> None:
        """PPE detector runs on even frames; helmet status is associated to each tracked person."""
        if self._frame_no % 2 == 0:
            with _INFER_LOCK:
                res = self._ppe.predict(frame, conf=0.35, imgsz=640, verbose=False, device=pick_device())[0]
            found = []
            if res.boxes is not None and len(res.boxes):
                names = res.names
                for b, c, k in zip(res.boxes.xyxy.cpu().numpy(), res.boxes.conf.cpu().numpy(),
                                   res.boxes.cls.cpu().numpy().astype(int)):
                    found.append({"box": b, "conf": float(c), "name": str(names[int(k)])})
            self._last_ppe = found
        persons = [d for d in dets if d["cat"] == "person"]
        assoc = ppe_mod.associate(persons, self._last_ppe)
        counts = dict(NO_PPE)
        now = time.time()
        for i, p in enumerate(persons):
            st = assoc[i]
            p["ppe"] = st
            counts[f"helmet_{st['helmet']}"] += 1
            if st["helmet"] != "no" or p["id"] is None:
                continue
            x1, _, x2, y2 = p["box"]
            fx, fy = (x1 + x2) / 2 / w, y2 / h
            for z in self.settings.get("zones", []):
                key = (p["id"], z["id"])
                if z.get("require_helmet") and point_in_polygon(fx, fy, z["points"]) and now - self._ppe_alerted.get(key, 0) > 60:
                    self._ppe_alerted[key] = now
                    self._emit(type="ppe_violation", label="person", track_id=p["id"], zone=z["name"],
                               severity="alert", capture=True,
                               message=f"Person #{p['id']} without helmet in “{z['name']}”")
        self.ppe_counts = counts

    # ------------------------------------------------------------- bookkeeping
    def _update_stats(self, dets: list[dict], faces: list[dict], w: int, h: int) -> None:
        cur = {c: 0 for c in CATEGORIES}
        for d in dets:
            cur[d["cat"]] += 1
            self.detections_total += 1
            tid = d["id"]
            if tid is not None and tid not in self._unique[d["cat"]]:
                self._unique[d["cat"]].add(tid)
                self._emit(type="new_track", label=d["label"], track_id=tid, confidence=round(d["conf"], 2),
                           message=f"New {d['label']} #{tid}")
            if d["cat"] != "object":
                x1, _, x2, y2 = d["box"]
                gx = min(HEAT_W - 1, max(0, int((x1 + x2) / 2 / w * HEAT_W)))
                gy = min(HEAT_H - 1, max(0, int(y2 / h * HEAT_H)))
                self.heat[gy, gx] += 1.0
        cur["face"] = len(faces)
        self.current = cur

    # ----------------------------------------------------------------- overlay
    def _draw(self, frame: np.ndarray, dets: list[dict], faces: list[dict], w: int, h: int) -> None:
        self._draw_rules(frame, w, h)
        for d in dets:
            x1, y1, x2, y2 = d["box"].astype(int)
            col = CATEGORY_COLORS.get(d["cat"], (200, 200, 200))
            uncertain = d["conf"] < UNCERTAIN_BELOW
            cv2.rectangle(frame, (x1, y1), (x2, y2), col, 1 if uncertain else 2)
            tag = f"{d['label']}{'?' if uncertain else ''}"
            if d["id"] is not None:
                tag += f" #{d['id']}"
            tag += f" {d['conf']:.2f}"
            if d.get("posture") and d["posture"] != "unknown":
                tag += f" · {d['posture']}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            ty = max(y1, th + 6)
            cv2.rectangle(frame, (x1, ty - th - 6), (x1 + tw + 6, ty), col, -1)
            cv2.putText(frame, tag, (x1 + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (10, 10, 10), 1, cv2.LINE_AA)
            st = d.get("ppe")
            if st:  # helmet chip under the box: green yes / red no / grey unknown (never guessed)
                txt, c2 = {"yes": ("helmet", (80, 200, 80)), "no": ("NO HELMET", (60, 60, 230)),
                           "unknown": ("helmet ?", (150, 150, 150))}[st["helmet"]]
                (tw2, th2), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                cv2.rectangle(frame, (x1, y2), (x1 + tw2 + 6, y2 + th2 + 6), c2, -1)
                cv2.putText(frame, txt, (x1 + 3, y2 + th2 + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        for pz in self._last_pose:
            kp = pz["kp"]
            for a, b in SKELETON:
                if kp[a][2] > 0.4 and kp[b][2] > 0.4:
                    cv2.line(frame, (int(kp[a][0]), int(kp[a][1])), (int(kp[b][0]), int(kp[b][1])), (0, 220, 255), 2, cv2.LINE_AA)
            for x, y, c in kp:
                if c > 0.4:
                    cv2.circle(frame, (int(x), int(y)), 3, (255, 255, 255), -1, cv2.LINE_AA)
        for f in faces:
            x1, y1, x2, y2 = f["box"].astype(int)
            col = CATEGORY_COLORS["face"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), col, 1)
            for (lx, ly) in f["lm"].astype(int):
                cv2.circle(frame, (lx, ly), 2, (0, 200, 255), -1)
            cv2.putText(frame, f"face {f['conf']:.2f}", (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1, cv2.LINE_AA)

    def _draw_rules(self, frame: np.ndarray, w: int, h: int) -> None:
        zones, lines = self.engine.zones, self.engine.lines
        if zones:
            overlay = frame.copy()
            for z in zones:
                pts = np.array([[int(x * w), int(y * h)] for x, y in z["points"]], np.int32)
                cv2.fillPoly(overlay, [pts], hex_to_bgr(z["color"]))
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, frame)
            for z in zones:
                col = hex_to_bgr(z["color"])
                pts = np.array([[int(x * w), int(y * h)] for x, y in z["points"]], np.int32)
                cv2.polylines(frame, [pts], True, col, 2, cv2.LINE_AA)
                st = self.engine.zone_stats.get(z["id"], {})
                label = f"{z['name']}: {st.get('occupancy', 0)}"
                tx, ty = int(pts[:, 0].min()), max(int(pts[:, 1].min()), 20)
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (tx, ty - th - 8), (tx + tw + 8, ty), col, -1)
                cv2.putText(frame, label, (tx + 4, ty - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1, cv2.LINE_AA)
        for ln in lines:
            p1 = (int(ln["p1"][0] * w), int(ln["p1"][1] * h))
            p2 = (int(ln["p2"][0] * w), int(ln["p2"][1] * h))
            col = (255, 200, 60)   # BGR for #3cc8ff, the same light blue the dashboard uses
            cv2.line(frame, p1, p2, col, 3, cv2.LINE_AA)
            # arrow from the midpoint towards the "in" side (the side where rules._side(p1, p2, pt) > 0)
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            n = max((dx * dx + dy * dy) ** 0.5, 1)
            mx, my = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
            cv2.arrowedLine(frame, (mx, my), (int(mx - dy / n * 28), int(my + dx / n * 28)), col, 2, cv2.LINE_AA, tipLength=0.4)
            st = self.engine.line_stats.get(ln["id"], {"in": 0, "out": 0})
            label = f"{ln['name']}  in {st['in']} / out {st['out']}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            ly = max(p1[1], 20)
            cv2.rectangle(frame, (p1[0], ly - th - 8), (p1[0] + tw + 8, ly), col, -1)
            cv2.putText(frame, label, (p1[0] + 4, ly - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 10, 10), 1, cv2.LINE_AA)
