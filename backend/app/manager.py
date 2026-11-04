"""Registry of cameras; owns lifecycle, persistence and the event queue."""
from __future__ import annotations

import json
import queue
import threading
import urllib.request
import uuid
from pathlib import Path

import cv2

from . import db
from .camera import CameraWorker
from .config import CATEGORIES, SAMPLE_DIR, UPLOAD_DIR
from .rules import sanitize_lines, sanitize_zones


def resolve_file(source: str) -> str:
    """Only allow files that live inside our own uploads/ or samples/ folders."""
    name = Path(source).name
    for base in (UPLOAD_DIR, SAMPLE_DIR):
        p = base / name
        if p.is_file():
            return str(p)
    raise ValueError(f"Video not found: {name}")


class CameraManager:
    def __init__(self) -> None:
        self.cameras: dict[str, CameraWorker] = {}
        self.meta: dict[str, dict] = {}
        self.events: "queue.Queue[dict]" = queue.Queue()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ events
    def _on_event(self, ev: dict) -> None:
        ev["id"] = db.add_event(ev)
        ev.setdefault("severity", "info")
        self.events.put(ev)
        if ev["severity"] == "alert":
            url = db.get_kv("webhook_url")
            if url:
                threading.Thread(target=self._post_webhook, args=(url, ev), daemon=True).start()

    @staticmethod
    def _post_webhook(url: str, ev: dict) -> None:
        """Generic JSON webhook. The `text` field makes it work as-is with Slack / Discord-compatible endpoints."""
        try:
            body = json.dumps({
                "text": f"[{ev['camera_name']}] {ev.get('message', ev['type'])}",
                "event": {k: ev.get(k) for k in ("id", "ts", "camera_id", "camera_name", "type", "label",
                                                 "track_id", "zone", "message", "severity", "image", "clip")},
            }).encode()
            req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as e:  # noqa: BLE001
            print(f"[webhook] delivery failed: {e}")

    # --------------------------------------------------------------- lifecycle
    def restore(self) -> None:
        for row in db.load_cameras():
            try:
                self._spawn(row["id"], row["name"], row["kind"], row["source"], row["settings"])
            except Exception as e:  # noqa: BLE001
                print(f"[restore] skipped {row['name']}: {e}")

    def _spawn(self, cam_id: str, name: str, kind: str, source: str, settings: dict) -> CameraWorker:
        src = resolve_file(source) if kind == "file" else source
        w = CameraWorker(cam_id, name, kind, src, settings, self._on_event)
        self.cameras[cam_id] = w
        self.meta[cam_id] = {"name": name, "kind": kind, "source": source}
        w.start()
        return w

    def add(self, name: str, kind: str, source: str, settings: dict | None = None) -> CameraWorker:
        if kind not in ("webcam", "file", "rtsp"):
            raise ValueError("kind must be webcam, file or rtsp")
        if kind == "webcam":
            source = str(int(source))
            if any(m["kind"] == "webcam" and m["source"] == source for m in self.meta.values()):
                raise ValueError(f"Webcam {source} is already added")
        if kind == "rtsp" and not source.lower().startswith(("rtsp://", "rtsps://", "http://", "https://")):
            raise ValueError("Stream URL must start with rtsp://, rtsps://, http:// or https://")
        cam_id = uuid.uuid4().hex[:8]
        with self._lock:
            w = self._spawn(cam_id, name.strip() or f"Camera {len(self.cameras) + 1}", kind, source, settings or {})
            db.save_camera(cam_id, w.name_, kind, source, w.settings)
        return w

    def remove(self, cam_id: str) -> None:
        w = self.cameras.pop(cam_id, None)
        self.meta.pop(cam_id, None)
        if w:
            w.stop()
        db.delete_camera(cam_id)

    def stop(self, cam_id: str) -> None:
        w = self._get(cam_id)
        w.stop()

    def start(self, cam_id: str) -> CameraWorker:
        old = self._get(cam_id)
        if old.is_alive():
            return old
        m = self.meta[cam_id]
        return self._spawn(cam_id, m["name"], m["kind"], m["source"], old.settings)

    def update_settings(self, cam_id: str, patch: dict) -> dict:
        w = self._get(cam_id)
        if "conf" in patch:
            w.settings["conf"] = max(0.05, min(0.95, float(patch["conf"])))
        if "faces" in patch:
            w.settings["faces"] = bool(patch["faces"])
        if "tracking" in patch:
            w.settings["tracking"] = bool(patch["tracking"])
        if "model" in patch:
            from . import detector
            m = str(patch["model"])
            if m and m not in {o["file"] for o in detector.options() if o["installed"]}:
                raise ValueError("Model not installed")
            w.settings["model"] = m
        if "pose" in patch:
            w.settings["pose"] = bool(patch["pose"])
            w.pose_error = None
        if "index" in patch:
            w.settings["index"] = bool(patch["index"])
            w.index_error = None
        if "privacy" in patch:
            w.settings["privacy"] = bool(patch["privacy"])
        if "health" in patch:
            w.settings["health"] = bool(patch["health"])
            w.monitor.reset()
        if "custom" in patch:
            from . import openvocab
            w.settings["custom"] = openvocab.clean_prompts(patch["custom"])
            w.custom_error = None
        if "custom_conf" in patch:
            w.settings["custom_conf"] = min(0.9, max(0.05, float(patch["custom_conf"])))
        if "atmosphere" in patch:
            w.settings["atmosphere"] = bool(patch["atmosphere"])
            w._atmos_ema, w._atmos_state, w._atmos_t, w._atmos_level = None, ("clear", "none"), 0.0, "clear"
        if "ppe" in patch:
            w.settings["ppe"] = bool(patch["ppe"])
            w.ppe_error = None
        if "zones" in patch or "lines" in patch:
            if "zones" in patch:
                w.settings["zones"] = sanitize_zones(patch["zones"])
            if "lines" in patch:
                w.settings["lines"] = sanitize_lines(patch["lines"])
            w.apply_rules()
        if "name" in patch and str(patch["name"]).strip():
            w.name_ = self.meta[cam_id]["name"] = str(patch["name"]).strip()
        db.update_camera_settings(cam_id, w.settings)
        return w.snapshot()

    def restart_all(self) -> None:
        """Restart every running camera (e.g. after switching detector weights). Stopped cameras stay stopped."""
        running = [cid for cid, w in self.cameras.items() if w.is_alive()]
        for cid in running:
            self.cameras[cid].stop()
        for cid in running:
            self.cameras[cid].join(timeout=15)
        for cid in running:
            m = self.meta.get(cid)
            if m:
                self._spawn(cid, m["name"], m["kind"], m["source"], self.cameras[cid].settings)

    def shutdown(self) -> None:
        for w in self.cameras.values():
            w.stop()

    def _get(self, cam_id: str) -> CameraWorker:
        w = self.cameras.get(cam_id)
        if not w:
            raise KeyError(cam_id)
        return w

    def get(self, cam_id: str) -> CameraWorker:
        return self._get(cam_id)

    # ------------------------------------------------------------------- views
    def snapshot(self) -> list[dict]:
        return [w.snapshot() for w in self.cameras.values()]

    def summary(self) -> dict:
        cams = self.snapshot()
        live = [c for c in cams if c["status"] == "live"]
        cur = {k: sum(c["current"].get(k, 0) for c in live) for k in CATEGORIES + ["face"]}
        uni = {k: sum(c["unique"].get(k, 0) for c in cams) for k in CATEGORIES}
        return {
            "cameras": len(cams),
            "live": len(live),
            "errors": sum(1 for c in cams if c["status"] == "error"),
            "current": cur,
            "unique": uni,
            "avg_fps": round(sum(c["fps"] for c in live) / len(live), 1) if live else 0,
            "avg_latency_ms": round(sum(c["latency_ms"] for c in live) / len(live), 1) if live else 0,
        }


def discover_webcams(max_index: int = 4, skip: set[int] | None = None) -> list[dict]:
    """Probe local camera indexes. Cameras already in use by the dashboard are reported as in_use."""
    skip = skip or set()
    found = []
    for i in range(max_index + 1):
        if i in skip:
            found.append({"index": i, "in_use": True})
            continue
        cap = cv2.VideoCapture(i)
        try:
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append({"index": i, "in_use": False})
        finally:
            cap.release()
    return found
