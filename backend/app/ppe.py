"""Optional PPE (helmet / vest) detector and person association.

There is no PPE model bundled: drop a custom-trained YOLO model at backend/models/ppe.pt.
Class names are mapped by keyword, so datasets with 'Hardhat' / 'NO-Hardhat' / 'Safety Vest' etc. work.
A person with no matching detection is reported as 'unknown', never as 'no helmet'.
"""
from __future__ import annotations

import re

from .config import PPE_MODEL

HELMET_RE = re.compile(r"(hard[\s_-]?hat|helmet)", re.I)
NEG_RE = re.compile(r"(^no[\s_-]|^without|^non[\s_-]|missing)", re.I)
VEST_RE = re.compile(r"(vest|hi[\s_-]?vis)", re.I)


def available() -> bool:
    return PPE_MODEL.exists()


def parse_class(name: str) -> tuple[str, bool] | None:
    """-> (item, present) or None if the class is not PPE we care about."""
    neg = bool(NEG_RE.search(name.strip()))
    if HELMET_RE.search(name):
        return "helmet", not neg
    if VEST_RE.search(name):
        return "vest", not neg
    return None


def associate(persons: list[dict], ppe: list[dict]) -> dict[int, dict]:
    """Attach PPE detections to person boxes.

    helmet: its centre must fall in the top 35% of the person box (and horizontally inside it).
    vest:   its centre must fall in the torso band (20%-65%) of the person box.
    Returns {person_index: {"helmet": "yes"|"no"|"unknown", "vest": ...}}.
    """
    out: dict[int, dict] = {}
    for i, p in enumerate(persons):
        x1, y1, x2, y2 = p["box"]
        h = max(y2 - y1, 1)
        res = {"helmet": "unknown", "vest": "unknown"}
        best = {"helmet": 0.0, "vest": 0.0}
        for d in ppe:
            parsed = parse_class(d["name"])
            if not parsed:
                continue
            item, present = parsed
            cx, cy = (d["box"][0] + d["box"][2]) / 2, (d["box"][1] + d["box"][3]) / 2
            if not (x1 <= cx <= x2):
                continue
            rel = (cy - y1) / h
            band = (-0.1, 0.35) if item == "helmet" else (0.2, 0.65)
            if band[0] <= rel <= band[1] and d["conf"] > best[item]:
                best[item] = d["conf"]
                res[item] = "yes" if present else "no"
        out[i] = res
    return out
