"""Zone / line-crossing / dwell-time rules evaluated on tracked detections.

Zones and lines are stored with normalised (0-1) coordinates so they are independent of the
stream resolution. A tracked object's *foot point* (bottom-centre of its box) is used for zone
membership and line crossing, which matches how people stand on the ground plane.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

ZONE_COLORS = ["#3dd6c6", "#ffb020", "#ff5ac8", "#5a78ff", "#e6e650", "#ff5d5d"]
CLASS_CHOICES = {"person", "car", "truck", "bus", "motorcycle", "bicycle", "animal", "object"}


def point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


def _side(p1, p2, pt) -> float:
    return (p2[0] - p1[0]) * (pt[1] - p1[1]) - (p2[1] - p1[1]) * (pt[0] - p1[0])


def segments_cross(a1, a2, b1, b2) -> bool:
    d1, d2 = _side(b1, b2, a1), _side(b1, b2, a2)
    d3, d4 = _side(a1, a2, b1), _side(a1, a2, b2)
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def sanitize_zones(raw) -> list[dict]:
    out = []
    for i, z in enumerate(raw or []):
        pts = [[min(max(float(p[0]), 0), 1), min(max(float(p[1]), 0), 1)] for p in z.get("points", [])][:50]
        if len(pts) < 3:
            continue
        out.append({
            "id": str(z.get("id") or uuid.uuid4().hex[:6]),
            "name": str(z.get("name") or f"Zone {i + 1}")[:40],
            "points": pts,
            "classes": [c for c in z.get("classes", ["person"]) if c in CLASS_CHOICES] or ["person"],
            "color": str(z.get("color") or ZONE_COLORS[i % len(ZONE_COLORS)])[:9],
            "alert_on_enter": bool(z.get("alert_on_enter", False)),
            "dwell_s": max(0.0, min(float(z.get("dwell_s") or 0), 3600)),     # 0 = off
            "max_occupancy": max(0, min(int(z.get("max_occupancy") or 0), 999)),  # 0 = off
            "require_helmet": bool(z.get("require_helmet", False)),
        })
    return out[:12]


def sanitize_lines(raw) -> list[dict]:
    out = []
    for i, ln in enumerate(raw or []):
        try:
            p1 = [min(max(float(ln["p1"][0]), 0), 1), min(max(float(ln["p1"][1]), 0), 1)]
            p2 = [min(max(float(ln["p2"][0]), 0), 1), min(max(float(ln["p2"][1]), 0), 1)]
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        if abs(p1[0] - p2[0]) + abs(p1[1] - p2[1]) < 0.02:
            continue
        out.append({
            "id": str(ln.get("id") or uuid.uuid4().hex[:6]),
            "name": str(ln.get("name") or f"Line {i + 1}")[:40],
            "p1": p1, "p2": p2,
            "classes": [c for c in ln.get("classes", ["person"]) if c in CLASS_CHOICES] or ["person"],
            "alert": bool(ln.get("alert", False)),
        })
    return out[:12]


class RuleEngine:
    """Feed it tracked detections each frame; it emits events and keeps live counters."""

    GONE_AFTER = 2.0  # seconds without a track before it is considered to have left

    def __init__(self, emit: Callable[..., None]) -> None:
        self.emit = emit
        self.zones: list[dict] = []
        self.lines: list[dict] = []
        self.zone_stats: dict[str, dict] = {}
        self.line_stats: dict[str, dict] = {}
        self._tracks: dict[tuple, dict] = {}   # (cat, id) -> state
        self._over_capacity: set[str] = set()

    def configure(self, zones: list[dict], lines: list[dict]) -> None:
        self.zones, self.lines = zones, lines
        self.zone_stats = {z["id"]: {"occupancy": 0, "entries": 0} for z in zones}
        self.line_stats = {ln["id"]: {"in": 0, "out": 0} for ln in lines}
        self._tracks.clear()
        self._over_capacity.clear()

    def reset(self) -> None:
        self.configure(self.zones, self.lines)

    def update(self, dets: list[dict], w: int, h: int, now: float | None = None) -> None:
        if not self.zones and not self.lines:
            return
        now = now or time.time()
        seen = set()
        for d in dets:
            if d["id"] is None:
                continue
            key = (d["cat"], d["id"])
            seen.add(key)
            x1, y1, x2, y2 = d["box"]
            pt = ((x1 + x2) / 2 / w, y2 / h)
            st = self._tracks.setdefault(key, {"pt": pt, "zones": {}, "alerted": set(), "last": now})
            prev, st["pt"], st["last"] = st["pt"], pt, now

            for ln in self.lines:
                if d["cat"] not in ln["classes"] or prev == pt:
                    continue
                if segments_cross(prev, pt, ln["p1"], ln["p2"]):
                    direction = "in" if _side(ln["p1"], ln["p2"], pt) > 0 else "out"
                    self.line_stats[ln["id"]][direction] += 1
                    self.emit(type="line_cross", label=d["label"], track_id=d["id"], confidence=round(d["conf"], 2),
                              zone=ln["name"], severity="alert" if ln["alert"] else "info", capture=ln["alert"],
                              message=f"{d['label'].title()} #{d['id']} crossed “{ln['name']}” ({direction})")

            for z in self.zones:
                if d["cat"] not in z["classes"]:
                    continue
                inside = point_in_polygon(pt[0], pt[1], z["points"])
                since = st["zones"].get(z["id"])
                if inside and since is None:
                    st["zones"][z["id"]] = now
                    self.zone_stats[z["id"]]["entries"] += 1
                    self.emit(type="zone_enter", label=d["label"], track_id=d["id"], confidence=round(d["conf"], 2),
                              zone=z["name"], severity="alert" if z["alert_on_enter"] else "info", capture=z["alert_on_enter"],
                              message=f"{d['label'].title()} #{d['id']} entered “{z['name']}”")
                elif not inside and since is not None:
                    del st["zones"][z["id"]]
                    self.emit(type="zone_exit", label=d["label"], track_id=d["id"], zone=z["name"],
                              message=f"{d['label'].title()} #{d['id']} left “{z['name']}” after {now - since:.0f}s")
                elif inside and z["dwell_s"] and (key, z["id"]) not in st["alerted"] and now - since >= z["dwell_s"]:
                    st["alerted"].add((key, z["id"]))
                    self.emit(type="dwell", label=d["label"], track_id=d["id"], zone=z["name"], severity="alert", capture=True,
                              message=f"{d['label'].title()} #{d['id']} in “{z['name']}” for over {z['dwell_s']:.0f}s")

        # tracks that vanished: close their zones
        for key in [k for k, v in self._tracks.items() if k not in seen and now - v["last"] > self.GONE_AFTER]:
            del self._tracks[key]

        # live occupancy + capacity alerts
        for z in self.zones:
            occ = sum(1 for k, v in self._tracks.items() if z["id"] in v["zones"] and k in seen)
            self.zone_stats[z["id"]]["occupancy"] = occ
            if z["max_occupancy"]:
                if occ > z["max_occupancy"] and z["id"] not in self._over_capacity:
                    self._over_capacity.add(z["id"])
                    self.emit(type="capacity", zone=z["name"], severity="alert", capture=True,
                              message=f"“{z['name']}” over capacity: {occ} (limit {z['max_occupancy']})")
                elif occ <= z["max_occupancy"]:
                    self._over_capacity.discard(z["id"])

    def snapshot(self) -> dict:
        return {"zones": self.zone_stats, "lines": self.line_stats}
