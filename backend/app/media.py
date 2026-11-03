"""Alert snapshots and short video clips (a few seconds before and after the trigger)."""
from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections import deque

import cv2
import numpy as np

from .config import MEDIA_DIR

MAX_FILES = 300
COOLDOWN_S = 10.0   # alerts closer together than this share one clip


def _cleanup() -> None:
    files = sorted(MEDIA_DIR.glob("*"), key=lambda p: p.stat().st_mtime)
    for p in files[:-MAX_FILES]:
        p.unlink(missing_ok=True)


def _write_clip(frames: list[tuple[float, bytes]], path) -> None:
    try:
        if len(frames) < 3:
            return
        span = max(frames[-1][0] - frames[0][0], 0.5)
        fps = max(4.0, min(30.0, len(frames) / span))
        first = cv2.imdecode(np.frombuffer(frames[0][1], np.uint8), cv2.IMREAD_COLOR)
        h, w = first.shape[:2]
        tmp = path.with_suffix(".tmp.mp4")
        vw = cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
        for _, jpg in frames:
            img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
            if img is not None and img.shape[:2] == (h, w):
                vw.write(img)
        vw.release()
        ff = shutil.which("ffmpeg")
        if ff:  # browsers need H.264; OpenCV's mp4v is not playable everywhere
            r = subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(tmp), "-c:v", "libx264",
                                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
                               capture_output=True, timeout=60)
            tmp.unlink(missing_ok=True)
            if r.returncode != 0:
                path.unlink(missing_ok=True)
        else:
            tmp.replace(path)
        _cleanup()
    except Exception as e:  # noqa: BLE001
        print(f"[clip] failed: {e}")


class ClipRecorder:
    def __init__(self, cam_id: str, pre_s: float = 5.0, post_s: float = 4.0) -> None:
        self.cam_id, self.pre_s, self.post_s = cam_id, pre_s, post_s
        self.buf: deque[tuple[float, bytes]] = deque()
        self.pending: list[dict] = []
        self._last_trigger = 0.0
        self._last_clip: str | None = None
        self._lock = threading.Lock()

    def push(self, ts: float, jpg: bytes) -> None:
        with self._lock:
            self.buf.append((ts, jpg))
            while self.buf and ts - self.buf[0][0] > self.pre_s:
                self.buf.popleft()
            done = []
            for p in self.pending:
                p["frames"].append((ts, jpg))
                if ts >= p["end"]:
                    done.append(p)
            for p in done:
                self.pending.remove(p)
                threading.Thread(target=_write_clip, args=(p["frames"], p["path"]), daemon=True).start()

    def trigger(self, now: float) -> tuple[str | None, str | None]:
        """Save a snapshot now and schedule a clip. Returns (image_name, clip_name)."""
        with self._lock:
            if not self.buf:
                return None, None
            stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
            img_name = f"{self.cam_id}_{stamp}_{int(now * 1000) % 1000:03d}.jpg"
            (MEDIA_DIR / img_name).write_bytes(self.buf[-1][1])
            if self._last_clip and now - self._last_trigger < COOLDOWN_S:
                return img_name, self._last_clip
            clip_name = f"{self.cam_id}_{stamp}.mp4"
            self._last_trigger, self._last_clip = now, clip_name
            self.pending.append({"frames": list(self.buf), "end": now + self.post_s, "path": MEDIA_DIR / clip_name})
            return img_name, clip_name
