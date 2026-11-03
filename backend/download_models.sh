#!/usr/bin/env bash
# Downloads model weights into backend/models/ (YOLO11n object detector + YuNet face detector).
set -e
cd "$(dirname "$0")/models"
[ -f yolo11n.pt ]   || curl -L --fail -o yolo11n.pt  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
[ -f yunet.onnx ]   || curl -L --fail -o yunet.onnx  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
echo "models ready"
