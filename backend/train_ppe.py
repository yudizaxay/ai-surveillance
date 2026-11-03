#!/usr/bin/env python
"""Fine-tune a helmet / PPE detector and install it as backend/models/ppe.pt.

You need a labelled dataset in YOLO format (images + .txt labels + a data .yaml). Public PPE datasets exist
(e.g. on Roboflow Universe or Kaggle) — check each one's licence, and prefer footage from your own cameras:
a model trained on other sites' footage usually loses a lot of accuracy on yours.

Classes are matched by keyword, so names like  Hardhat / NO-Hardhat / Safety Vest / NO-Safety Vest  work.

    .venv/bin/python train_ppe.py --data /path/to/ppe/data.yaml --epochs 60
    .venv/bin/python evaluate.py --weights models/ppe.pt --data /path/to/ppe/data.yaml --name "PPE · site A"
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

from app.camera import pick_device
from app.config import MODEL_DIR, PPE_MODEL


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dataset yaml in YOLO format")
    ap.add_argument("--base", default=str(MODEL_DIR / "yolo11n.pt"), help="weights to start from")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    a = ap.parse_args()

    model = YOLO(a.base)
    res = model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=pick_device(),
                      project=str(MODEL_DIR / "runs"), name="ppe", exist_ok=True)
    best = Path(res.save_dir) / "weights" / "best.pt"
    shutil.copy(best, PPE_MODEL)
    print(f"Installed {PPE_MODEL}. Restart the backend, then enable Helmet / PPE on a camera.")
    print("Names in the model:", YOLO(str(PPE_MODEL)).names)


if __name__ == "__main__":
    main()
