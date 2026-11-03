#!/usr/bin/env bash
# Downloads model weights into backend/models/: YOLO11m + YOLO11n (object detectors), YOLO11n-pose, YuNet (faces).
set -e
cd "$(dirname "$0")/models"
MODELS="yolo11m yolo11n yolo11n-pose"
[ "${WITH_XL:-0}" = "1" ] && MODELS="$MODELS yolo11x"   # WITH_XL=1 ./download_models.sh for the most accurate (largest) model
for m in $MODELS; do
  [ -f $m.pt ] || curl -L --fail -o $m.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/$m.pt
done
[ -f yunet.onnx ]   || curl -L --fail -o yunet.onnx  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
echo "models ready"
