"""Camera health and tamper checks from the video itself (no model).

Looks for the things that make a camera silently useless:
  frozen   - the source keeps sending the identical picture,
  blocked  - lens covered / black / completely flat image,
  blurred  - sharpness collapsed against the camera's own recent baseline (spray, fog on the lens, defocus),
  moved    - the scene structure no longer matches the baseline (camera knocked or turned).

"blurred" and "moved" are relative to a slowly updated baseline of what this camera normally looks like, so
they need a few minutes of healthy video first. A heavy scene change (lights switched off, a bus parked in
front of the lens) can look like tampering; alerts are confirmed over several readings to reduce that.
"""
from __future__ import annotations

import cv2
import numpy as np

SAMPLE_EVERY = 2.0     # seconds between checks
FROZEN_SECONDS = 8.0
CONFIRM = 3            # consecutive identical verdicts before an alert is raised

ISSUES = ("frozen", "blocked", "blurred", "moved")


def _thumb(frame: np.ndarray) -> np.ndarray:
    g = cv2.cvtColor(cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return g


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float32).ravel() - a.mean()
    b = b.astype(np.float32).ravel() - b.mean()
    d = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / d) if d > 1e-6 else 1.0


class HealthMonitor:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.prev: np.ndarray | None = None
        self.same_since: float | None = None
        self.base_sharp: float | None = None
        self.base_struct: np.ndarray | None = None
        self.healthy_samples = 0
        self.last_t = 0.0
        self.verdict = "ok"
        self.pending = ("ok", 0)
        self.confirmed = "ok"
        self.metrics: dict = {}

    def update(self, frame: np.ndarray, now: float) -> tuple[str, bool] | None:
        """Feed a frame. Returns (confirmed_status, changed) when a new sample was taken, else None."""
        if now - self.last_t < SAMPLE_EVERY:
            return None
        self.last_t = now
        g = _thumb(frame)
        mean, std = float(g.mean()), float(g.std())
        sharp = float(cv2.Laplacian(cv2.GaussianBlur(g, (3, 3), 0), cv2.CV_32F).var())
        struct = cv2.GaussianBlur(g, (0, 0), 3)

        diff = float(np.abs(g.astype(np.int16) - self.prev.astype(np.int16)).mean()) if self.prev is not None else 99.0
        self.prev = g
        if diff < 0.02:
            self.same_since = self.same_since if self.same_since is not None else now
        else:
            self.same_since = None

        verdict = "ok"
        if mean < 6 or std < 3:
            verdict = "blocked"
        elif self.same_since is not None and now - self.same_since >= FROZEN_SECONDS:
            verdict = "frozen"
        elif self.base_sharp is not None and self.healthy_samples >= 30:
            if sharp < 0.25 * self.base_sharp and self.base_sharp > 4:
                verdict = "blurred"
            elif self.base_struct is not None and _ncc(struct, self.base_struct) < 0.35:
                verdict = "moved"

        if verdict == "ok":   # learn what "normal" looks like, slowly
            self.healthy_samples += 1
            a = 0.05 if self.healthy_samples < 30 else 0.01
            self.base_sharp = sharp if self.base_sharp is None else (1 - a) * self.base_sharp + a * sharp
            self.base_struct = struct.astype(np.float32) if self.base_struct is None else (
                (1 - a) * self.base_struct + a * struct.astype(np.float32))

        self.metrics = {"sharpness": round(sharp, 1), "brightness": round(mean, 1), "contrast": round(std, 1),
                        "frame_diff": round(diff, 3)}
        self.verdict = verdict
        self.pending = (verdict, self.pending[1] + 1) if verdict == self.pending[0] else (verdict, 1)
        changed = False
        if self.pending[1] >= (1 if verdict == "frozen" else CONFIRM) and verdict != self.confirmed:
            self.confirmed, changed = verdict, True
        return self.confirmed, changed
