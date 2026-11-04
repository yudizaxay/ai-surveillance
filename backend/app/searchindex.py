"""Natural-language search over what the cameras have seen (CLIP image / text embeddings).

While a camera has "Searchable footage" switched on, a thumbnail of the clean frame (after privacy blur, if on) and
the crops of its largest detections are embedded with CLIP every few seconds and stored with a small thumbnail.
A text query is embedded with the same model and ranked by cosine similarity, so "person in a red jacket" or
"white van" can be found without having labelled anything.

CLIP matches overall appearance, not exact attributes: colours, objects and scenes work well, counting, tiny
objects and text do not. Scores are similarities, not probabilities.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from . import db
from .config import INDEX_DIR, MODEL_DIR

INDEX_EVERY = float(os.getenv("VM_INDEX_EVERY", "10"))   # seconds between indexed frames per camera
MAX_FRAMES = int(os.getenv("VM_INDEX_MAX_FRAMES", "4000"))
MAX_CROPS = 6
DUPLICATE_SIM = 0.985   # skip a frame that is practically identical to the previous indexed one

_lock = threading.Lock()
_state: dict = {"model": None, "preprocess": None, "device": "cpu", "error": None}


def available() -> bool:
    try:
        import clip  # noqa: F401
    except Exception:
        return False
    return (MODEL_DIR / "clip" / "ViT-B-32.pt").exists()


def _load():
    if _state["model"] is not None:
        return _state["model"], _state["preprocess"]
    import clip
    import torch
    dev = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model, pre = clip.load("ViT-B/32", device="cpu", jit=False, download_root=str(MODEL_DIR / "clip"))
    model = model.float().to(dev).eval()
    _state.update(model=model, preprocess=pre, device=dev, error=None)
    return model, pre


def _encode_images(bgr_list: list[np.ndarray]) -> np.ndarray:
    import torch
    from PIL import Image
    with _lock:
        model, pre = _load()
        batch = torch.stack([pre(Image.fromarray(cv2.cvtColor(b, cv2.COLOR_BGR2RGB))) for b in bgr_list]).to(_state["device"])
        with torch.no_grad():
            f = model.encode_image(batch)
        f = f / f.norm(dim=-1, keepdim=True)
    return f.cpu().numpy().astype(np.float32)


def encode_text(query: str) -> np.ndarray:
    import clip
    import torch
    with _lock:
        model, _ = _load()
        toks = clip.tokenize([query, f"a photo of {query}", f"a security camera image of {query}"], truncate=True).to(_state["device"])
        with torch.no_grad():
            f = model.encode_text(toks)
        f = f / f.norm(dim=-1, keepdim=True)
        f = f.mean(dim=0)
        f = f / f.norm()
    return f.cpu().numpy().astype(np.float32)


def index_frame(cam_id: str, cam_name: str, frame: np.ndarray, dets: list[dict], last_full: np.ndarray | None):
    """Embed the frame and its biggest detections. Returns the new full-frame embedding (or None if skipped)."""
    h, w = frame.shape[:2]
    crops, meta = [], []
    for d in sorted(dets, key=lambda d: -(d["box"][2] - d["box"][0]) * (d["box"][3] - d["box"][1])):
        if len(crops) >= MAX_CROPS:
            break
        if d["conf"] < 0.4 or d["cat"] == "object":
            continue
        x1, y1, x2, y2 = d["box"]
        pw, ph = (x2 - x1) * 0.08, (y2 - y1) * 0.08
        a, b, c, e = max(0, int(x1 - pw)), max(0, int(y1 - ph)), min(w, int(x2 + pw)), min(h, int(y2 + ph))
        if c - a < 36 or e - b < 36:
            continue
        crops.append(frame[b:e, a:c])
        meta.append((d["label"], a / w, b / h, c / w, e / h))
    embs = _encode_images([frame] + crops)
    full = embs[0]
    if last_full is not None and float(full @ last_full) > DUPLICATE_SIM and not crops:
        return full
    ts = time.time()
    name = f"{int(ts * 1000)}_{cam_id[:8]}.jpg"
    scale = 480 / max(w, 1)
    thumb = cv2.resize(frame, (480, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(INDEX_DIR / name), thumb, [cv2.IMWRITE_JPEG_QUALITY, 72])
    rows = [("frame", None, 0.0, 0.0, 1.0, 1.0, embs[0].astype(np.float16).tobytes())]
    for (label, x1, y1, x2, y2), v in zip(meta, embs[1:]):
        rows.append(("crop", label, x1, y1, x2, y2, v.astype(np.float16).tobytes()))
    db.add_frame(ts, cam_id, cam_name, name, rows)
    for old in db.prune_frames(MAX_FRAMES):
        (INDEX_DIR / old).unlink(missing_ok=True)
    return full


def search(query: str, limit: int = 24, camera_id: str | None = None, minutes: int | None = None) -> list[dict]:
    since = time.time() - minutes * 60 if minutes else 0.0
    rows = db.index_rows(since, camera_id)
    if not rows:
        return []
    q = encode_text(query)
    mat = np.vstack([np.frombuffer(r["emb"], dtype=np.float16).astype(np.float32) for r in rows])
    sims = mat @ q
    best: dict[int, tuple[float, int]] = {}
    for i, s in enumerate(sims):
        fid = rows[i]["frame_id"]
        if fid not in best or s > best[fid][0]:
            best[fid] = (float(s), i)
    out = []
    for fid, (s, i) in sorted(best.items(), key=lambda kv: -kv[1][0])[:limit]:
        r = rows[i]
        crop = r["kind"] == "crop"
        out.append({"frame_id": fid, "score": round(s, 4), "ts": r["ts"], "camera_id": r["camera_id"],
                    "camera_name": r["camera_name"], "thumb": r["thumb"], "label": r["label"] if crop else None,
                    "box": [r["x1"], r["y1"], r["x2"], r["y2"]] if crop else None})
    return out


def clear(camera_id: str | None = None) -> int:
    names = db.clear_index(camera_id)
    for n in names:
        (INDEX_DIR / n).unlink(missing_ok=True)
    return len(names)
