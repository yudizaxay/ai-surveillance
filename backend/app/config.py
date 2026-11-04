"""Static configuration: paths, COCO class groups, colours."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("VM_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
SAMPLE_DIR = DATA_DIR / "samples"
MODEL_DIR = BASE_DIR / "models"
DB_PATH = DATA_DIR / "surveillance.db"

FACE_MODEL = MODEL_DIR / "yunet.onnx"
POSE_WEIGHTS = MODEL_DIR / "yolo11n-pose.pt"
PPE_MODEL = MODEL_DIR / "ppe.pt"          # optional, custom-trained (not bundled)
MEDIA_DIR = DATA_DIR / "media"
EVAL_DIR = DATA_DIR / "eval"
INDEX_DIR = DATA_DIR / "index"   # thumbnails for the searchable-footage index

for _d in (DATA_DIR, UPLOAD_DIR, SAMPLE_DIR, MODEL_DIR, MEDIA_DIR, EVAL_DIR, INDEX_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# COCO class id -> (label, category)
# All of these come from the *pre-trained* COCO model. Nothing here is custom-trained.
COCO_CLASSES: dict[int, tuple[str, str]] = {
    0: ("person", "person"),
    1: ("bicycle", "bicycle"),
    2: ("car", "car"),
    3: ("motorcycle", "motorcycle"),
    5: ("bus", "bus"),
    7: ("truck", "truck"),
    14: ("bird", "animal"),
    15: ("cat", "animal"),
    16: ("dog", "animal"),
    17: ("horse", "animal"),
    18: ("sheep", "animal"),
    19: ("cow", "animal"),
    20: ("elephant", "animal"),
    21: ("bear", "animal"),
    22: ("zebra", "animal"),
    23: ("giraffe", "animal"),
    24: ("backpack", "object"),
    26: ("handbag", "object"),
    28: ("suitcase", "object"),
}
DETECT_CLASS_IDS = list(COCO_CLASSES.keys())

CATEGORIES = ["person", "car", "truck", "bus", "motorcycle", "bicycle", "animal", "object"]

# BGR colours per category for the overlay
CATEGORY_COLORS = {
    "person": (80, 220, 100),
    "car": (255, 170, 60),
    "truck": (60, 140, 255),
    "bus": (60, 200, 255),
    "motorcycle": (255, 90, 200),
    "bicycle": (230, 230, 80),
    "animal": (90, 120, 255),
    "object": (200, 200, 200),
    "face": (255, 255, 255),
}

# Detections below this are drawn as "uncertain" (thin box, "?" label)
OBJECT_MIN_CONF = 0.5     # bags etc. are easily confused with other things: demand more evidence
UNCERTAIN_BELOW = 0.45
STREAM_MAX_WIDTH = 960
JPEG_QUALITY = 72
