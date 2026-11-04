"""Visibility / atmosphere estimate from a single camera frame (no model, pure image statistics).

Fog and haze scatter light, which leaves three measurable fingerprints:
  * the dark channel (per-pixel minimum over B,G,R) is high everywhere, because there are no truly dark pixels,
  * global contrast drops,
  * fine edges / texture fade.
These are combined into a 0-100 visibility index. If the scene is hazy, the colour of the veil is used to
guess its type: a neutral grey-white veil is fog; a yellow/brown veil is smog or dust (possible pollution).

This is a relative, camera-specific indicator. It is not a calibrated visibility distance in metres and it
cannot measure PM2.5 / AQI. Indoor, night-time and texture-less scenes (e.g. an empty sky) are unreliable.
"""
from __future__ import annotations

import cv2
import numpy as np

LEVELS = ("clear", "hazy", "foggy", "dense")


def level_for(visibility: float) -> str:
    if visibility >= 70:
        return "clear"
    if visibility >= 55:
        return "hazy"
    if visibility >= 35:
        return "foggy"
    return "dense"


def _veil_fraction(small: np.ndarray, gx: int = 8, gy: int = 6) -> float:
    """Share of an 8x6 block grid that is smooth, nearly colourless and not dark: what fog or haze looks like.
    Blue sky is excluded by its saturation; textured surfaces are excluded by their gradient."""
    g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    sx, sy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    grad = np.sqrt(sx * sx + sy * sy)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat, val = hsv[..., 1] / 255.0, hsv[..., 2] / 255.0
    H, W = g.shape
    bh, bw = max(1, H // gy), max(1, W // gx)
    hit = n = 0
    for i in range(gy):
        for j in range(gx):
            sl = (slice(i * bh, (i + 1) * bh), slice(j * bw, (j + 1) * bw))
            n += 1
            if grad[sl].mean() < 0.04 and sat[sl].mean() < 0.25 and val[sl].mean() > 0.25:
                hit += 1
    return hit / max(n, 1)


def analyze(frame: np.ndarray) -> dict:
    """Return visibility (0-100, higher is clearer), level, kind and the raw metrics."""
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (192, max(1, int(192 * h / w))), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    # 1) dark channel prior: min over colour channels, then a local minimum
    dark = cv2.erode(small.min(axis=2), np.ones((9, 9), np.uint8)).astype(np.float32) / 255.0
    dark_mean = float(dark.mean())

    # 2) global contrast (robust: 5th-95th percentile spread)
    lo, hi = np.percentile(gray, [5, 95])
    contrast = float(hi - lo)

    # 3) edge strength (mean gradient magnitude)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    edges = float(np.sqrt(gx * gx + gy * gy).mean())

    brightness = float(gray.mean())
    if brightness < 0.22:  # night / very dark: the statistics below are meaningless
        return {"visibility": None, "level": "night", "kind": "none", "dark": round(dark_mean, 3),
                "contrast": round(contrast, 3), "edges": round(edges, 3), "tint": 0.0}

    veil = _veil_fraction(small)
    haze = (
        0.25 * min(1.0, dark_mean / 0.60)
        + 0.35 * (1.0 - min(1.0, contrast / 0.50))
        + 0.40 * (1.0 - min(1.0, edges / 0.13))
    )
    visibility = 100 * (1.0 - min(1.0, max(0.0, haze)))
    # A sharp foreground (frosty branches, a fence, a nearby tree) can hide fog that has swallowed the rest of the
    # scene, so global averages read "clear". Haze is judged on the share of the image that is flat, grey and
    # bright-ish (the veil) as well, and the worse of the two wins.
    visibility = round(max(0.0, min(visibility, 100.0 - 170.0 * veil)), 1)
    level = level_for(visibility)

    # colour of the veil: look at the haziest (brightest-dark-channel) quarter of the image
    veil_mask = dark >= np.percentile(dark, 75)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    a_shift = float(lab[..., 1][veil_mask].mean() - 128)
    b_shift = float(lab[..., 2][veil_mask].mean() - 128)
    warm = b_shift  # +b is yellow
    kind = "none"
    if level != "clear":
        kind = "smog" if (warm > 9 and a_shift > -4) else "fog"

    return {
        "visibility": visibility, "level": level, "kind": kind,
        "dark": round(dark_mean, 3), "contrast": round(contrast, 3), "edges": round(edges, 3),
        "veil": round(veil, 2), "tint": round(warm, 1),
    }
