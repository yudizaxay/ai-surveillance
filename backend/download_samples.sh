#!/usr/bin/env bash
# Downloads a few public sample CCTV-style clips (Intel IoT devkit) into data/samples/
set -e
DEST="${VM_DATA_DIR:-$(dirname "$0")/data}/samples"
mkdir -p "$DEST" && cd "$DEST"
BASE=https://github.com/intel-iot-devkit/sample-videos/raw/master
for f in person-bicycle-car-detection store-aisle-detection worker-zone-detection car-detection; do
  [ -f "$f.mp4" ] || curl -sL --fail -o "$f.mp4" "$BASE/$f.mp4" && echo "ok $f"
done
