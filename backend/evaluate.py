#!/usr/bin/env python
"""Evaluate a YOLO detector on a labelled dataset and store the result for the dashboard's Evaluation page.

    .venv/bin/python evaluate.py --weights models/yolo11n.pt --data coco8.yaml --name "YOLO11n · COCO8 smoke test"
    .venv/bin/python evaluate.py --weights models/ppe.pt --data /path/to/ppe/data.yaml --name "PPE · site footage"

Precision / recall / F1 are reported at the confidence threshold you pass; mAP is threshold-free.
A result is only meaningful for the dataset it was measured on, so the dataset, size and thresholds are stored with it.
"""
import argparse
import json
import re
import time
from pathlib import Path

from ultralytics import YOLO, settings

from app.camera import pick_device
from app.config import DATA_DIR, EVAL_DIR

settings.update({"datasets_dir": str(DATA_DIR / "datasets")})   # keep downloaded datasets inside the project


def count_images(data: str) -> int | None:
    """Number of validation images in the dataset yaml (None if it cannot be determined)."""
    try:
        from ultralytics.data.utils import check_det_dataset
        val = Path(check_det_dataset(data)["val"])
        return sum(1 for f in val.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"})
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True, help="YOLO dataset yaml (e.g. coco8.yaml or your own)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--conf", type=float, default=0.25, help="threshold for the P / R / F1 figures")
    ap.add_argument("--iou", type=float, default=0.6)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    model = YOLO(a.weights)
    m = model.val(data=a.data, conf=a.conf, iou=a.iou, imgsz=a.imgsz, device=pick_device(), plots=False, verbose=False)
    box = m.box
    names = m.names
    per_class = []
    for i, c in enumerate(box.ap_class_index):
        p, r = float(box.p[i]), float(box.r[i])
        per_class.append({
            "class": names[int(c)], "precision": round(p, 3), "recall": round(r, 3),
            "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
            "map50": round(float(box.ap50[i]), 3), "map50_95": round(float(box.ap[i]), 3),
            "instances": int(m.nt_per_class[int(c)]) if hasattr(m, "nt_per_class") else None,
        })
    result = {
        "name": a.name or f"{Path(a.weights).stem} · {Path(a.data).stem}",
        "weights": Path(a.weights).name, "dataset": a.data,
        "images": count_images(a.data), "conf_threshold": a.conf, "iou_threshold": a.iou, "imgsz": a.imgsz,
        "device": pick_device(), "ts": time.time(),
        "overall": {"precision": round(float(box.mp), 3), "recall": round(float(box.mr), 3),
                    "f1": round(float(box.f1.mean()), 3) if hasattr(box, "f1") else None,
                    "map50": round(float(box.map50), 3), "map50_95": round(float(box.map), 3)},
        "speed_ms": {k: round(float(v), 1) for k, v in m.speed.items()},
        "per_class": per_class, "note": a.note,
    }
    slug = re.sub(r"[^a-z0-9]+", "-", result["name"].lower()).strip("-")[:60]
    out = EVAL_DIR / f"{slug}.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"saved {out}")
    print(json.dumps(result["overall"]))


if __name__ == "__main__":
    main()
