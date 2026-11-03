"""Posture from COCO-17 keypoints (YOLO-Pose). Rule-based, so it can say 'unknown' instead of guessing."""
from __future__ import annotations

import math

import numpy as np

# COCO keypoint indices
L_SH, R_SH, L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANK, R_ANK = 5, 6, 11, 12, 13, 14, 15, 16
MIN_KP_CONF = 0.4

SKELETON = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12),
            (11, 13), (13, 15), (12, 14), (14, 16), (0, 1), (0, 2), (1, 3), (2, 4)]


def _mid(kp: np.ndarray, a: int, b: int):
    pts = [kp[i] for i in (a, b) if kp[i][2] >= MIN_KP_CONF]
    if not pts:
        return None
    return float(np.mean([p[0] for p in pts])), float(np.mean([p[1] for p in pts]))


def classify_posture(kp: np.ndarray) -> str:
    """Returns standing | sitting | bending | lying | unknown."""
    sh, hip = _mid(kp, L_SH, R_SH), _mid(kp, L_HIP, R_HIP)
    if sh is None or hip is None:
        return "unknown"
    dx, dy = hip[0] - sh[0], hip[1] - sh[1]
    torso = math.hypot(dx, dy)
    if torso < 8:                       # keypoints collapsed / person too small to judge
        return "unknown"
    angle = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))   # 0 = upright torso, 90 = horizontal
    if angle >= 60:
        return "lying"
    knee, ankle = _mid(kp, L_KNEE, R_KNEE), _mid(kp, L_ANK, R_ANK)
    if angle >= 35:
        return "bending"
    if knee is not None:
        thigh_drop = (knee[1] - hip[1]) / torso     # ~0.9-1.0 when standing, <0.5 when seated
        if thigh_drop < 0.45:
            return "sitting"
        if thigh_drop >= 0.6 and (ankle is not None or knee is not None):
            return "standing"
    return "unknown"


def iou(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0
