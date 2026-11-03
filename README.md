# Vision Monitor — AI Video Analytics Demo

A multi-camera AI video-analytics proof of concept. Connect any number of webcams, video files or
RTSP streams and watch real-time object detection, tracking and counters on one dashboard.

> **Proof of concept.** No accuracy figure is claimed. Performance depends on camera angle, lighting,
> resolution and hardware, and must be evaluated on representative footage before any real use.

## Features

- **Multi-camera dashboard** — grid of live tiles (Auto / 1–4 columns), per-camera status, FPS, latency,
  resolution and uptime; add, start, stop and remove cameras at runtime.
- **Sources** — local webcams (auto-discovered), uploaded videos, bundled sample clips, RTSP / HTTP streams.
- **Detection** — person, car, truck, bus, motorcycle, bicycle, animals and bags with boxes, labels and
  confidence. Low-confidence boxes are drawn thin with a `?` instead of being presented as certain.
- **Tracking** — ByteTrack gives persistent track IDs.
- **Counters** — "now in frame" and "unique tracked" are kept separate; a frame-by-frame count is not a
  unique-person count.
- **Face detection** — locates faces only (YuNet). **No identity recognition.**
- **Event log** — new-track and camera online/offline/error events stored in SQLite, shown live and
  exportable as CSV.
- **Per-camera settings** — confidence threshold, tracking and face detection toggles.

## What is pre-trained and what is not

| Capability | Status |
|---|---|
| Person, vehicles, animals, bags | Pre-trained COCO model (YOLO11n) |
| Tracking | ByteTrack (Ultralytics) |
| Face detection | Pre-trained YuNet |
| Helmet / PPE, pose, zones & line-crossing, clothing categories, activity recognition | **Not implemented** — need custom-trained models / rules (roadmap) |

Face and clothing analysis is deliberately limited: the demo does not identify people and does not infer
religion, ethnicity, intent or suspiciousness from appearance.

## Architecture

```
webcam / file / RTSP -> OpenCV capture -> YOLO11 + ByteTrack -> YuNet faces -> overlay -> MJPEG
                                              |
                                  stats + events -> SQLite -> FastAPI -> WebSocket -> React dashboard
```

- `backend/` — FastAPI service, one worker thread per camera, SQLite event store.
- `frontend/` — React + TypeScript + Vite dashboard (live stats over WebSocket, video over MJPEG).

## Run it

Requirements: [uv](https://docs.astral.sh/uv/), Node 18+. Apple Silicon (MPS), NVIDIA (CUDA) or CPU.

```bash
./setup.sh   # venv, dependencies, model weights, sample videos, npm install
./run.sh     # API on :8000, dashboard on :5173
```

Open <http://localhost:5173>, click **Add camera**, and pick a sample video, a webcam or a stream URL.

On macOS, allow camera access for your terminal (System Settings → Privacy & Security → Camera) to use a webcam.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/cameras` | list cameras with live stats |
| POST | `/api/cameras` | add `{name, kind: webcam\|file\|rtsp, source}` |
| POST | `/api/cameras/upload` | upload a video (multipart) |
| POST | `/api/cameras/{id}/start` · `/stop` | control a camera |
| PATCH | `/api/cameras/{id}` | `{conf, faces, tracking, name}` |
| DELETE | `/api/cameras/{id}` | remove |
| GET | `/api/cameras/{id}/stream` | MJPEG stream with overlays |
| GET | `/api/discover` · `/api/samples` | local webcams · sample clips |
| GET | `/api/events` · `/api/report.csv` | event log · CSV export |
| WS | `/ws` | stats (1 Hz) and events |

## Privacy and responsible use

Use footage only where you have the authority to do so. Restrict access to video and event records,
define retention and deletion, and keep a human in the loop for any consequential decision.

## Roadmap

Helmet / PPE detector (custom-trained), pose estimation, zones and line-crossing, face-visibility
classification, alert rules, multi-stream GPU scaling.
