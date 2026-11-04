"""Open-vocabulary detection: find objects by typing a name, with no training (YOLO-World).

The text prompts are turned into CLIP text embeddings once; after that the detector is as fast as a normal
YOLO model. It is a zero-shot model, so it is less accurate than a model trained on the object, and it works
best with short concrete nouns ("forklift", "hard hat", "fire extinguisher"). Scores are lower than for COCO
classes, which is why the dashboard exposes its own confidence slider.
"""
from __future__ import annotations

import re
import threading
from collections import OrderedDict
from pathlib import Path

from .config import MODEL_DIR

WORLD_WEIGHTS = MODEL_DIR / "yolov8s-worldv2.pt"
MAX_PROMPTS = 8
MAX_LEN = 40
_CACHE_SIZE = 2          # each cached model keeps its own CLIP text encoder in memory (~350 MB)

_cache: "OrderedDict[tuple[str, ...], object]" = OrderedDict()
_lock = threading.Lock()


def available() -> bool:
    return WORLD_WEIGHTS.exists()


def clean_prompts(raw) -> list[str]:
    """Normalise user input: trim, lowercase, drop duplicates / odd characters, cap count and length."""
    out: list[str] = []
    for item in raw or []:
        s = re.sub(r"[^\w\s\-']", "", str(item), flags=re.UNICODE).strip().lower()[:MAX_LEN]
        s = re.sub(r"\s+", " ", s)
        if s and s not in out:
            out.append(s)
        if len(out) >= MAX_PROMPTS:
            break
    return out


def get(prompts: tuple[str, ...]):
    """Return a YOLO-World model whose classes are exactly `prompts` (cached)."""
    with _lock:
        if prompts in _cache:
            _cache.move_to_end(prompts)
            return _cache[prompts]
        import ultralytics.nn.text_model as tm
        from ultralytics import YOLOWorld
        tm.WEIGHTS_DIR = Path(MODEL_DIR)          # keep the CLIP weights next to the other models
        model = YOLOWorld(str(WORLD_WEIGHTS))
        model.set_classes(list(prompts))
        _cache[prompts] = model
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
        return model
