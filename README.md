<p align="center">
  <img src="docs/assets/banner.svg" alt="Vision Monitor — multi-camera AI video analytics" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="YOLO11" src="https://img.shields.io/badge/Ultralytics-YOLO11-111F68">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/status-proof%20of%20concept-orange">
</p>

<h3 align="center">One dashboard to monitor every camera — live detection, tracking, counters and analytics.</h3>

<p align="center">
  <img src="docs/assets/dashboard-live.png" alt="Live monitor: four cameras with detections, counters and event log" width="100%">
</p>

> **Proof of concept.** This project makes no accuracy claim. Results depend on camera angle, lighting,
> resolution and hardware, and must be evaluated on representative footage before any real-world use.

---

## Contents

[Features](#features) · [Screenshots](#screenshots) · [What is pre-trained](#what-is-pre-trained-and-what-is-not) · [Quick start](#quick-start) · [Using the dashboard](#using-the-dashboard) · [Architecture](#architecture) · [API](#api) · [Configuration](#configuration) · [Project layout](#project-layout) · [Privacy](#privacy-and-responsible-use) · [Roadmap](#roadmap)

## Features

| | |
|---|---|
| **Multi-camera monitoring** | Connect any number of cameras at once and watch them in one grid (Auto, 1–4 columns). Each tile shows status, FPS, latency, resolution, uptime and live counters. Add, start, stop and remove cameras at runtime. |
| **Flexible sources** | Local webcams (auto-discovered), uploaded video files, bundled sample clips, and RTSP / HTTP streams. |
| **Real-time detection** | People, cars, trucks, buses, motorcycles, bicycles, animals and bags, with bounding boxes, labels and confidence. Low-confidence boxes are drawn thin with a `?` instead of being shown as certain. |
| **Tracking** | ByteTrack assigns persistent track IDs per camera. |
| **Honest counters** | "Now in frame" and "unique tracked" are always shown separately. A frame-by-frame count is not a unique-person count. |
| **Face detection** | Locates faces and landmarks only. **No identity recognition.** |
| **Analytics** | Trend charts for objects in view, throughput and latency; a class breakdown; per-camera table. |
| **Event log** | New-track and camera online / offline / error events stored in SQLite. Searchable, filterable, exportable as CSV. |
| **Per-camera controls** | Confidence threshold, tracking on/off and face detection on/off, adjustable live. |

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/assets/camera-detail.png" alt="Camera detail view with per-class counts and settings"><br><sub><b>Camera detail</b> — per-class counts, confidence slider, tracking and face toggles.</sub></td>
    <td width="50%"><img src="docs/assets/dashboard-analytics.png" alt="Analytics page with trend charts"><br><sub><b>Analytics</b> — objects in view, unique tracked, FPS and latency over time.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/dashboard-events.png" alt="Events page with search and filters"><br><sub><b>Events</b> — searchable, filterable log with CSV export.</sub></td>
    <td width="50%"><img src="docs/assets/dashboard-system.png" alt="System page with models and capabilities"><br><sub><b>System</b> — device, models, capabilities and per-camera runtime.</sub></td>
  </tr>
</table>

The dashboard is responsive; the sidebar collapses to icons on tablets and a top bar on phones.

## What is pre-trained and what is not

| Capability | Status |
|---|---|
| Person, vehicles, animals, bags | Pre-trained COCO model (YOLO11n) |
| Multi-object tracking | ByteTrack (Ultralytics) |
| Face detection | Pre-trained YuNet |
| Helmet / PPE detection | **Not implemented** — needs a custom-trained model and a labelled dataset |
| Pose, activity recognition, zones, line-crossing, clothing categories | **Not implemented** — roadmap |

The dashboard states the same limitations on its **System** page.

## Quick start

**Requirements:** [uv](https://docs.astral.sh/uv/) and Node.js 18+. Runs on Apple Silicon (MPS), NVIDIA (CUDA) or CPU.

```bash
git clone <this repo> && cd ai-surveillance
./setup.sh      # Python 3.12 venv, dependencies, model weights, sample videos, npm install
./run.sh        # API on :8000, dashboard on :5173
```

Open **<http://localhost:5173>**, click **Add camera**, and choose a sample video, a webcam or a stream URL.

<details>
<summary>Manual setup</summary>

```bash
# backend
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
./download_models.sh        # YOLO11n + YuNet into backend/models/
./download_samples.sh       # optional demo clips into backend/data/samples/
.venv/bin/uvicorn app.main:app --port 8000

# frontend (second terminal)
cd frontend && npm install && npm run dev
```
</details>

**Webcams on macOS:** allow camera access for your terminal in *System Settings → Privacy & Security → Camera*.

## Using the dashboard

| Page | What it is for |
|---|---|
| **Live monitor** | Camera grid, all-camera totals and the live event feed. Double-click a tile (or use the expand icon) for the detail view. |
| **Analytics** | Trends over the last 5–60 minutes, unique-by-class breakdown and a per-camera table. |
| **Events** | Full event history with search, camera and type filters, and CSV export. |
| **System** | Service health, inference device, models, capability status and per-camera runtime. |

Pages are deep-linkable (`#/live`, `#/analytics`, `#/events`, `#/system`).

**Adding cameras**

| Source | How |
|---|---|
| Sample video | *Add camera → Sample videos* |
| Webcam | *Add camera → Local webcam* (scans indexes 0–4) |
| Video file | *Add camera → Upload video* (mp4, mov, avi, mkv, webm; up to 300 MB). Files loop, with the tracker reset on each loop. |
| IP / CCTV camera | *Add camera → RTSP / URL*, e.g. `rtsp://user:pass@192.168.1.10:554/stream1` |

## Architecture

```mermaid
flowchart LR
    A[Webcam / video file / RTSP] --> B[OpenCV capture<br/>one thread per camera]
    B --> C[YOLO11 + ByteTrack]
    B --> D[YuNet face detector]
    C --> E[Overlay + stats + events]
    D --> E
    E -->|MJPEG| F[React dashboard]
    E -->|SQLite| G[(Event store)]
    G --> H[FastAPI]
    E -->|WebSocket 1 Hz| F
    H -->|REST| F
```

- Each camera runs in its own worker thread. Inference is serialised through one lock so several cameras
  can share a single GPU / accelerator safely.
- Video reaches the browser as MJPEG; stats and events arrive over a WebSocket, with automatic reconnect.
- Frames are downscaled to a maximum width of 960 px for speed and bandwidth.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Device, model names, uptime |
| GET | `/api/cameras` | All cameras with live stats |
| POST | `/api/cameras` | Add `{name, kind: webcam\|file\|rtsp, source}` |
| POST | `/api/cameras/upload` | Upload a video (multipart: `file`, `name`) |
| POST | `/api/cameras/{id}/start` · `/stop` | Control a camera |
| PATCH | `/api/cameras/{id}` | `{conf, faces, tracking, name}` |
| DELETE | `/api/cameras/{id}` | Remove a camera |
| GET | `/api/cameras/{id}/stream` | MJPEG stream with overlays |
| GET | `/api/cameras/{id}/snapshot` | Latest annotated frame (JPEG) |
| GET | `/api/discover` · `/api/samples` | Local webcams · sample clips |
| GET | `/api/summary` · `/api/history?minutes=` | Aggregated stats · trend data |
| GET | `/api/events` · `/api/report.csv` | Event log · CSV export |
| WS | `/ws` | `stats` (1 Hz) and `event` messages |

Interactive docs are served at <http://localhost:8000/docs>.

## Configuration

Tunables live in `backend/app/config.py`:

| Setting | Default | Meaning |
|---|---|---|
| `YOLO_WEIGHTS` | `models/yolo11n.pt` | Swap for `yolo11s.pt` / `yolo11m.pt` for accuracy at lower FPS |
| `UNCERTAIN_BELOW` | `0.45` | Boxes below this confidence are drawn as uncertain |
| `STREAM_MAX_WIDTH` | `960` | Frame width cap for inference and streaming |
| `JPEG_QUALITY` | `72` | MJPEG quality |

Per-camera confidence, tracking and face detection are changed live from the camera detail view.

## Project layout

```
backend/            FastAPI service
  app/camera.py       per-camera worker: capture, detect, track, overlay
  app/manager.py      camera registry, lifecycle, persistence
  app/main.py         REST, MJPEG and WebSocket endpoints
  app/db.py           SQLite (cameras, events)
frontend/           React + TypeScript + Vite dashboard
  src/pages.tsx       Live, Analytics, Events, System pages
  src/components.tsx  camera tile, detail view, add-camera dialog
  src/charts.tsx      dependency-free SVG charts
docs/assets/        logo, banner and screenshots
```

## Privacy and responsible use

- Use footage only where you have the authority and permission to do so.
- Face detection locates faces; it does not identify anyone. Face recognition is intentionally not included.
- The system does not infer religion, ethnicity, identity, intent or suspiciousness from appearance or clothing.
- Restrict access to video and event records, define retention and deletion, and keep a human in the loop
  for any consequential decision.

## Roadmap

- [ ] Helmet / PPE detector (custom-trained) with person association
- [ ] Pose estimation and posture
- [ ] Zones, line-crossing and dwell-time rules with alerts
- [ ] Face-visibility (occluded / not visible) classification
- [ ] Evaluation harness: precision, recall, mAP per class and camera condition
- [ ] Authentication and role-based access for multi-user deployments

## Credits

Built with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), [OpenCV](https://opencv.org/)
(YuNet face detector from [opencv_zoo](https://github.com/opencv/opencv_zoo)), [FastAPI](https://fastapi.tiangolo.com/),
[React](https://react.dev/) and [Lucide](https://lucide.dev/) icons. Demo clips are downloaded from
[intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos); refer to that repository for
their terms. Ultralytics YOLO is AGPL-3.0 licensed — review the license before commercial use.
