"""Which YOLO weights the camera workers use. Switchable at runtime from the dashboard (System page)."""
from __future__ import annotations

import os

from . import db
from .config import MODEL_DIR

# file -> (label, hint)
CHOICES = {
    "yolo11n.pt": ("Fast", "Nano. Highest FPS, but misses many small or overhead (top-down) objects."),
    "yolo11m.pt": ("Balanced", "Medium. Good accuracy on overhead views at a moderate speed cost (default)."),
    "yolo11x.pt": ("Most accurate", "Extra-large. Best recall, slowest. Use on a GPU or with few cameras."),
}
DEFAULT = os.getenv("VM_MODEL", "yolo11m.pt")


def options() -> list[dict]:
    return [{"file": f, "label": lab, "hint": hint, "installed": (MODEL_DIR / f).exists()} for f, (lab, hint) in CHOICES.items()]


def current() -> str:
    name = db.get_kv("detector") or DEFAULT
    if (MODEL_DIR / name).exists():
        return name
    for f in CHOICES:               # fall back to whatever is installed
        if (MODEL_DIR / f).exists():
            return f
    return name


def path():
    return MODEL_DIR / current()
