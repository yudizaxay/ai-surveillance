<p align="center">
  <img src="docs/assets/banner.svg" alt="Vision Monitor — multi-camera AI video analytics" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="YOLO11" src="https://img.shields.io/badge/Ultralytics-YOLO11-111F68">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/status-proof%20of%20concept-orange">
</p>

<h3 align="center">One dashboard to monitor every camera — live detection, tracking, zones, alerts and analytics.</h3>

<p align="center">
  <img src="docs/assets/dashboard-live.png" alt="Live monitor: four cameras with detections, a zone, lines, pose and the event log" width="100%">
</p>

> **Proof of concept.** This project makes no accuracy claim. Results depend on camera angle, lighting,
> resolution and hardware, and must be evaluated on representative footage before any real-world use.
> See [Known limitations](#known-limitations) for what does not work well yet.

---

## Contents

[Features](#features) · [Screenshots](#screenshots) · [What is pre-trained](#what-is-pre-trained-and-what-is-not) · [Quick start](#quick-start) · [Using the dashboard](#using-the-dashboard) · [Zones, lines and alerts](#zones-lines-and-alerts) · [Models and performance](#models-and-performance) · [Search](#natural-language-search) · [Detect anything](#detect-anything) · [Camera health](#camera-health-and-tamper) · [Privacy mode](#privacy-mode) · [Daily report](#daily-report) · [Weather & visibility](#weather-and-visibility-fog-haze-smog) · [Helmet / PPE](#helmet--ppe) · [Evaluation](#evaluation) · [Login and roles](#login-and-roles) · [Docker](#docker) · [Architecture](#architecture) · [API](#api) · [Configuration](#configuration) · [Project layout](#project-layout) · [Known limitations](#known-limitations) · [Privacy](#privacy-and-responsible-use) · [Roadmap](#roadmap)

## Features

| | |
|---|---|
| **Multi-camera monitoring** | Any number of cameras in one grid (Auto, 1–4 columns). Each tile shows status, FPS, latency, resolution, uptime and live counters. Add, start, stop and remove cameras at runtime. |
| **Flexible sources** | Local webcams (auto-discovered), uploaded video files, bundled sample clips, and RTSP / HTTP streams. |
| **Real-time detection** | People, cars, trucks, buses, motorcycles, bicycles, animals and bags with boxes, labels and confidence. Low-confidence boxes are drawn thin with a `?` instead of being shown as certain. |
| **Tracking** | ByteTrack assigns persistent track IDs per camera. |
| **Honest counters** | “Now in frame” and “unique tracked” are always separate. A frame-by-frame count is not a unique-person count. |
| **Zones and line crossing** | Draw polygons and lines on a live frame. Get occupancy, entries, in / out counts, dwell time and capacity limits. |
| **Alerts** | Rule-based alerts with a snapshot and a short video clip (before and after), a dashboard banner and sound, acknowledgement, and an optional Slack-compatible webhook. |
| **Pose and posture** | Skeleton overlay, standing / sitting / bending / lying, and possible-fall alerts that explicitly ask for human review. |
| **Heatmap** | Where people and vehicles spent time, per camera. |
| **Natural-language search** | Search what the cameras have seen in plain words (“person in an orange vest”, “white car”). CLIP finds matching moments across cameras, with the matching object boxed. |
| **Detect anything** | Type an object name (“forklift”, “hard hat”, “telescope dome”) and an open-vocabulary model (YOLO-World) finds it. No training, no fixed list of detectors. |
| **Camera health & tamper** | Alerts when a camera freezes, is blocked, blurs or is moved, plus automatic reconnect with back-off for streams that drop. |
| **Privacy mode** | Pixelates faces (and the head of people whose face is not detected) before frames are streamed, saved or recorded. |
| **Daily report** | One-click HTML report (print to PDF) with activity per hour, detections per camera, alerts and snapshots. |
| **Weather & visibility** | Optional per-camera fog / haze / smog estimate (0-100 visibility index) with alerts. No model needed. |
| **Face detection** | Locates faces and landmarks only. **No identity recognition.** |
| **Helmet / PPE pipeline** | Ready for a custom-trained model. Reports `unknown` rather than guessing. No model is bundled. |
| **Analytics and events** | Trend charts, per-camera breakdown, searchable event log, CSV export. |
| **Evaluation page** | Precision, recall, F1 and mAP per class, stored with their dataset and thresholds. |
| **Login and roles** | Optional admin / viewer accounts (viewers are read-only). |
| **Model choice** | Fast / Balanced / Most accurate, globally or per camera. |

## Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/assets/zone-editor.png" alt="Zone editor drawing a restricted area"><br><sub><b>Zone editor</b> — draw zones and lines on a live frame; set entry alerts, dwell and capacity limits.</sub></td>
    <td width="50%"><img src="docs/assets/dashboard-alerts.png" alt="Alerts page with snapshots"><br><sub><b>Alerts</b> — snapshots, clips, acknowledgement and filters.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/camera-detail.png" alt="Camera detail with pose, zone and settings"><br><sub><b>Camera detail</b> — per-class counts, pose, zones, model and thresholds.</sub></td>
    <td width="50%"><img src="docs/assets/heatmap.png" alt="Heatmap view"><br><sub><b>Heatmap</b> — where activity concentrates.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/alert-clip.png" alt="Alert review with video clip"><br><sub><b>Alert review</b> — play the clip before deciding.</sub></td>
    <td width="50%"><img src="docs/assets/dashboard-analytics.png" alt="Analytics trends"><br><sub><b>Analytics</b> — objects in view, FPS and latency over time.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/dashboard-evaluation.png" alt="Evaluation page"><br><sub><b>Evaluation</b> — metrics with their dataset and thresholds.</sub></td>
    <td width="50%"><img src="docs/assets/dashboard-system.png" alt="System page"><br><sub><b>System</b> — models, capabilities, webhook and device.</sub></td>
  </tr>
</table>

The dashboard is responsive: the sidebar collapses to icons on tablets and to a top bar on phones.

## What is pre-trained and what is not

| Capability | Status |
|---|---|
| Person, vehicles, animals, bags | Pre-trained COCO model (YOLO11) |
| Multi-object tracking | ByteTrack (Ultralytics) |
| Face detection | Pre-trained YuNet |
| Pose and posture | Pre-trained YOLO11-pose keypoints + rule-based posture |
| Zones, line crossing, dwell, capacity, alerts | Rule engine (not a model) |
| Detect anything by typing | Pre-trained YOLO-World (zero-shot, open vocabulary); less accurate than a trained model |
| Camera health, fog / haze, privacy blur | Image statistics and the face detector (no extra model) |
| Helmet / PPE | **No model bundled.** Pipeline and training script included; needs your own labelled data |
| Clothing / covering categories | **Intentionally not built** (sensitive attribute) |
| Identity / face recognition | **Intentionally not built** |
| Activity recognition (running, lifting) | Not implemented |

The dashboard states the same on its **System** page.

## Quick start

**Requirements:** [uv](https://docs.astral.sh/uv/), Node.js 18+, `git` and `ffmpeg` (ffmpeg is used for alert clips). Runs on Apple Silicon (MPS), NVIDIA (CUDA) or CPU. The first setup downloads about 0.6 GB of models and dependencies (YOLO weights, plus the CLIP text encoder used by search and “Detect anything”).

```bash
git clone <this repo> && cd ai-surveillance
./setup.sh      # Python 3.12 venv, dependencies, model weights, sample videos, npm install (a few minutes)
./run.sh        # API on :8000, dashboard on :5173
```

Open **<http://localhost:5173>**, click **Add camera**, and choose a sample video, a webcam or a stream URL. Try the **Search** page after switching on *Searchable footage* for a camera, and the *Detect anything* box in a camera's detail panel.

### Try a live stream

No camera at hand? **Add camera → Stream** accepts any RTSP / HTTP URL. These public webcams were reachable when this README was written and are good for trying the pipeline (they are third-party streams, so they can go offline or change scene at any time):

| Stream | URL | Scene |
|---|---|---|
| Lake, Slovakia (also good for the fog / visibility demo) | `rtsp://stream.strba.sk:1935/strba/VYHLAD_JAZERO.stream` | 1280×720 |
| Observatory, South Africa (good for *Detect anything*: “telescope dome”) | `rtsp://196.21.92.82/axis-media/media.amp` | 1024×640 |
| University plaza, San Diego | `rtsp://132.239.12.145/axis-media/media.amp` | 1280×800 |

Test a URL outside the app with `ffprobe -rtsp_transport tcp "<url>"`. If it reports `403` or `401`, the stream needs access the server will not give; the app cannot work around that. For a stream that never goes offline, loop a local video through an RTSP server such as [MediaMTX](https://github.com/bluenviron/mediamtx) with `ffmpeg`.

<details>
<summary>Manual setup</summary>

```bash
# backend
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
PY=.venv/bin/python ./download_models.sh   # YOLO11m/n, pose, YuNet, YOLO-World + CLIP into backend/models/
PY=.venv/bin/python WITH_XL=1 ./download_models.sh   # optional: also the most accurate model (yolo11x, ~110 MB)
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
| **Live monitor** | Camera grid, all-camera totals and the live event feed. Click the expand icon (or double-click a tile) for the detail view. |
| **Alerts** | Every alert with its snapshot and clip. Acknowledge individually or all at once; sound on / off. |
| **Analytics** | Trends over the last 5–60 minutes, unique-by-class breakdown and a per-camera table. |
| **Events** | Full history with search, camera and type filters, and CSV export. |
| **Evaluation** | Stored precision / recall / F1 / mAP runs. |
| **System** | Service health, detector choice, capability status, alert webhook and per-camera runtime. |

Pages are deep-linkable (`#/live`, `#/alerts`, `#/analytics`, `#/events`, `#/evaluation`, `#/system`).

| Add a camera from | How |
|---|---|
| Sample video | *Add camera → Sample videos* |
| Webcam | *Add camera → Local webcam* (scans indexes 0–4) |
| Video file | *Add camera → Upload video* (mp4, mov, avi, mkv, webm; up to 300 MB). Files loop in real time and the tracker resets on each loop. |
| IP / CCTV camera | *Add camera → RTSP / URL*, e.g. `rtsp://user:pass@192.168.1.10:554/stream1` |

## Zones, lines and alerts

Open a camera’s detail view and choose **Edit zones & lines**. Draw on a clean frame, drag handles to reshape, and
set rules per shape:

| Rule | Where | Raises |
|---|---|---|
| Alert on entry | zone | `zone_enter` alert |
| Dwell longer than N seconds | zone | `dwell` alert (once per track) |
| More than N inside | zone | `capacity` alert |
| No helmet (needs a PPE model) | zone | `ppe_violation` alert |
| Alert on every crossing | line | `line_cross` alert (an arrow marks the “in” direction; flip it if needed) |
| Possible fall | pose | `fall` alert after ~1.5 s lying down |
| Camera failure | camera | `camera_error` alert |

Zone membership and line crossing use each object’s **foot point** (bottom-centre of its box). Each shape counts
only the classes you choose. Every alert stores a snapshot and a clip (about 5 s before and 4 s after) that you can
review from the Alerts page; alerts that arrive within 10 s of each other share a clip. Clips need `ffmpeg`
(otherwise the snapshot is shown).

**Webhook.** Under *System → Alert webhook* set an `http(s)` URL. Alerts are POSTed as JSON
(`{"text": "...", "event": {...}}`), compatible with Slack-style incoming webhooks. The URL is stored on the server and
never shown again.

Alerts are prompts for a person to look, not conclusions. Possible-fall and no-helmet alerts can be wrong; review the
clip before acting.

## Models and performance

COCO-trained detectors are weakest on **overhead (top-down) views**, which the bundled *Highway* sample uses.
Measured on that clip (8 frames with a visible car, 16 empty frames, confidence 0.25):

| Model | Car frames detected | False-positive frames | Notes |
|---|---|---|---|
| `yolo11n` (Fast) | 1 / 8 | 0 / 16 | Highest FPS |
| `yolo11m` (Balanced, default) | 4–6 / 8 | 0 / 16 | ~45 ms per frame on Apple MPS |
| `yolo11x` (Most accurate) | 7 / 8 | 0 / 16 | ~165 ms per frame on Apple MPS |

A small hand-checked sample, not a benchmark. The fix that actually scales is fine-tuning on overhead footage.
Choose the model globally under *System → Detection model*, or **per camera** in its detail view (for example the
overhead camera on *Most accurate* and the rest on *Balanced*). Switching restarts the affected cameras.

Cameras share one accelerator and inference is serialised, so FPS per camera falls as cameras are added. Expect
roughly 3–5 FPS per camera with four cameras on a laptop GPU using the Balanced model. Video files are dropped to
real-time speed rather than played in slow motion. Pose runs on alternate frames.

## Natural-language search

Open **Search**, type what you want to find and press Enter. Turn on **Searchable footage** for a camera (or press **Index all cameras**) and every few seconds a small thumbnail of the frame, plus the crops of its largest detections, is embedded with CLIP and stored. A query is embedded with the same model and matched by similarity, so nothing has to be labelled in advance.

<p align="center"><img src="docs/assets/search.png" alt="Search results for a person wearing an orange safety vest" width="860"></p>

- **What it is good at:** colours, objects and scenes (“person in an orange vest”, “white car”, “stacks of plates”, “empty warehouse floor”). Results show the matching person or vehicle boxed, the camera and the time.
- **Checked on the bundled clips:** “person wearing an orange safety vest” returns the Worker-Zone camera, “white car” and “bicycle” the road camera, “stacks of white plates” the store. A search takes well under a second.
- **What it is not:** it does not read text, count things, or understand exact attributes. Scores are similarities, not probabilities, so weak matches are dimmed and labelled. Something nobody filmed still returns its closest look-alikes; check the picture.
- **Storage and privacy:** only thumbnails (480 px) and 512-number embeddings are stored, the newest 4000 frames (`VM_INDEX_MAX_FRAMES`) at one per `VM_INDEX_EVERY` seconds (default 10) per camera. Indexing is opt-in per camera, uses the privacy-blurred frame when Privacy mode is on, and **Clear** deletes everything. Nearly identical frames are skipped.

## Detect anything

In a camera's detail panel, open **Detect anything**, type an object (“forklift”, “fire extinguisher”, “hard hat”, “umbrella”, “telescope dome”) and press Add. The camera starts looking for it immediately; matches get violet boxes, a count chip and an event.

<p align="center"><img src="docs/assets/detect-anything.png" alt="Open-vocabulary detection of a typed object" width="860"></p>

- **How:** YOLO-World turns the typed text into CLIP embeddings once, then runs as fast as a normal detector (about every third frame). Up to 8 phrases per camera, with their own confidence slider.
- **Why it matters:** fixed detector lists (people, cars, PPE…) cannot find something nobody trained for. This can.
- **Honest limits:** it is zero-shot, so it misses more and is less precise than a model trained on the object. Short concrete nouns work best; abstract phrases do not. Cluttered scenes (plates on a shelf) can defeat it. Verify before relying on it.
- **Setup:** `backend/download_models.sh` fetches the ~25 MB detector and the ~340 MB CLIP text encoder once.

## Camera health and tamper

Always on for live sources (webcam, RTSP / HTTP); off by default for looping video files, which would look “frozen” or “moved”. Every ~2 s the frame is checked for:

| State | Meaning |
|---|---|
| **frozen** | the source keeps sending the identical picture |
| **blocked** | the lens is covered, or the image is black / completely flat |
| **blurred** | sharpness collapsed against the camera's own recent baseline |
| **moved** | the scene no longer matches the baseline (camera knocked or turned) |

An alert (with snapshot and clip) fires after repeated readings, and a recovery event when it clears. If a stream stops delivering frames, the camera **reconnects automatically** with growing delays and reports each attempt. Credentials in stream URLs are masked in alerts and reports.

Limits: “blurred” and “moved” need about a minute of healthy video to learn a baseline, and a large legitimate change (lights off, a bus parked in front of the camera) can look like tampering.

## Privacy mode

Turn on **Privacy mode** per camera. Faces are pixelated before the frame is drawn, streamed, stored as a snapshot or recorded in a clip, so nothing un-blurred leaves the pipeline. If a person's face is not detected (turned away, far, small), the head region of the person box is pixelated instead.

It is best effort: a face that neither detector finds is not covered, so do not treat it as a guarantee of anonymisation.

## Daily report

**Events → Daily report** opens a self-contained HTML page for the last 24 h (`/api/report.html?hours=1..168`): key numbers, activity per hour, detections per camera, alerts by type, camera health and the latest alerts with snapshots. Use **Print / Save as PDF** in the browser for a PDF.

<p align="center"><img src="docs/assets/daily-report.png" alt="Daily report" width="640"></p>

## Weather and visibility (fog, haze, smog)

<p align="center"><img src="docs/assets/weather-visibility.png" alt="Fog detected on a camera with a visibility gauge" width="860"></p>

Turn on **Weather & visibility** in a camera's detail panel. Every ~2 seconds the frame is analysed with plain image statistics (no neural network): the dark channel (haze lifts the darkest pixels), global contrast and edge strength are combined into a **0-100 visibility index**. The result is shown as a chip on the tile, a gauge with a trend line in the detail view, and an alert after three consistent readings (so a passing cloud does not flicker).

- **Levels:** clear, hazy, foggy, dense. Night frames are reported as "night" and not assessed.
- **Fog vs smog:** a neutral grey-white veil is labelled fog; a warm yellow/brown veil is labelled smog / possible pollution.
- **Calibration:** checked against a real foggy camera and against synthetic fog (scattering model) at several densities; the score falls steadily as fog thickens.

A sharp foreground (frosty branches, a fence) can hide fog over the rest of the scene, so the score also looks at how much of the frame is flat, grey and bright (the veil); the worse of the two readings wins.

What it is not: a distance in metres, and not an air-quality measurement. It cannot read PM2.5 / AQI, and a warm tint is only a hint of smog or dust. Use it on outdoor cameras with a view into the distance. An overcast grey sky, a flat grey overhead view of asphalt and indoor cameras can read as haze and give unreliable scores, which is why it is off by default. For real air quality, use a sensor or an air-quality API.

## Helmet / PPE

No PPE model is bundled, because helmet detection needs a detector trained on labelled PPE data from conditions like
yours. The rest is in place: the detector hook, person ↔ helmet association (helmet in the top 35 % of the person
box), per-zone “no helmet” alerts and a status chip on each person.

A person with no matching detection is shown as **helmet ? (unknown)**, never as “no helmet”.

```bash
cd backend
.venv/bin/python train_ppe.py --data /path/to/ppe/data.yaml --epochs 60      # writes models/ppe.pt
.venv/bin/python evaluate.py --weights models/ppe.pt --data /path/to/ppe/data.yaml --name "PPE · site A"
```

Class names are matched by keyword (`Hardhat`, `NO-Hardhat`, `Safety Vest`, …). Restart the backend, then switch on
*Helmet / PPE* for a camera. Prefer footage from your own cameras; check any public dataset’s licence.

## Evaluation

```bash
cd backend
.venv/bin/python evaluate.py --weights models/yolo11m.pt --data my_data.yaml --name "Site A · night"
```

Results appear on the **Evaluation** page together with the dataset, image count and thresholds they were measured
with. The bundled entry is a COCO8 smoke test (4 validation images): it proves the pipeline works, and says
nothing about accuracy on your cameras. Do not quote one accuracy figure without the dataset, class, threshold and
method behind it.

## Login and roles

Authentication is **off by default** (fine on a trusted local machine). To switch it on, set:

| Variable | Meaning |
|---|---|
| `VM_ADMIN_PASSWORD` | Enables login. The `admin` account can change everything. |
| `VM_ADMIN_USER` | Admin username (default `admin`). |
| `VM_VIEWER_PASSWORD` | Optional read-only `viewer` account (cannot add / stop / remove cameras, edit rules, or acknowledge). |
| `VM_VIEWER_USER` | Viewer username (default `viewer`). |

Sessions are signed HttpOnly cookies, failed logins are rate-limited, and every API write checks the role. This is
deliberately small: put the service behind HTTPS (a reverse proxy) before exposing it beyond a trusted network.

```bash
VM_ADMIN_PASSWORD='choose-a-strong-one' VM_VIEWER_PASSWORD='another-one' ./run.sh
```

## Docker

```bash
VM_ADMIN_PASSWORD='choose-a-strong-one' docker compose up --build
# open http://localhost:8000
```

One container serves the API and the built dashboard; state (cameras, events, uploads, clips) lives in the
`vm-data` volume. The image runs CPU inference with PyTorch’s CPU build and downloads the models at build time.
Local webcams are not available inside containers; use video files or RTSP streams. For NVIDIA GPUs install the CUDA
build of PyTorch in the image and add the usual `deploy.resources.reservations.devices` entry to the compose file.

## Architecture

```mermaid
flowchart LR
    A[Webcam / video file / RTSP] --> B[OpenCV capture<br/>one thread per camera]
    B --> C[YOLO11 + ByteTrack]
    B --> D[YuNet face detector]
    B --> P[Pose · PPE<br/>optional]
    C --> R[Rule engine<br/>zones · lines · dwell]
    P --> R
    R --> E[Overlay + stats + events]
    D --> E
    E -->|MJPEG| F[React dashboard]
    E -->|SQLite| G[(Events · cameras)]
    E -->|snapshots + clips| M[(Media)]
    R -->|alerts| W[Webhook]
    G --> H[FastAPI]
    E -->|WebSocket 1 Hz| F
    H -->|REST| F
```

- Each camera runs in its own worker thread. Inference is serialised through one lock so several cameras can share a
  single accelerator safely.
- Video reaches the browser as MJPEG; stats and events arrive over a WebSocket with automatic reconnect.
- Frames are downscaled to a maximum width of 960 px for speed and bandwidth.
- Zones and lines are stored per camera in normalised coordinates, independent of stream resolution.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Device, model names, uptime, auth state |
| GET | `/api/cameras` | All cameras with live stats |
| POST | `/api/cameras` | Add `{name, kind: webcam\|file\|rtsp, source}` |
| POST | `/api/cameras/upload` | Upload a video (multipart: `file`, `name`) |
| POST | `/api/cameras/{id}/start` · `/stop` | Control a camera |
| PATCH | `/api/cameras/{id}` | `{conf, faces, tracking, pose, ppe, atmosphere, health, privacy, index, custom, custom_conf, model, name, zones, lines}` |
| DELETE | `/api/cameras/{id}` | Remove a camera |
| GET | `/api/cameras/{id}/stream` | MJPEG stream with overlays |
| GET | `/api/cameras/{id}/snapshot[?raw=true]` | Latest frame (annotated, or clean for the zone editor) |
| GET | `/api/search?q=…&camera_id=&minutes=` · `/api/search/status` · DELETE `/api/search/index` | Natural-language search, index status, clear index |
| GET | `/api/report.html?hours=24` | Printable activity report |
| GET | `/api/cameras/{id}/atmosphere` | Visibility index now + recent history |
| GET | `/api/cameras/{id}/heatmap` · POST `…/heatmap/reset` | Heatmap image · reset |
| GET | `/api/discover` · `/api/samples` | Local webcams · sample clips |
| GET | `/api/summary` · `/api/history?minutes=` | Aggregated stats · trend data |
| GET | `/api/events` · `/api/report.csv` | Event log · CSV export |
| GET | `/api/alerts` · POST `/api/alerts/ack` | Alerts · acknowledge `{id}` or `{all: true}` |
| GET | `/api/media/{name}` | Alert snapshot / clip |
| GET/PUT | `/api/settings/detector` | Global detection model |
| GET/PUT | `/api/settings/webhook` · POST `…/test` | Alert webhook |
| GET | `/api/eval` | Stored evaluation runs |
| POST | `/api/auth/login` · `/logout` · GET `/api/auth/me` | Session |
| WS | `/ws` | `stats` (1 Hz) and `event` messages |

Interactive docs are served at <http://localhost:8000/docs>.

## Configuration

| Setting | Where | Default | Meaning |
|---|---|---|---|
| `VM_MODEL` | env | `yolo11m.pt` | Default detector weights (also switchable in the UI) |
| `VM_INDEX_EVERY` | env | `10` | Seconds between indexed frames per camera (search) |
| `VM_INDEX_MAX_FRAMES` | env | `4000` | Newest indexed frames kept for search |
| `VM_DATA_DIR` | env | `backend/data` | Database, uploads, clips, evaluation results |
| `VM_ADMIN_PASSWORD` etc. | env | unset | See [Login and roles](#login-and-roles) |
| `UNCERTAIN_BELOW` | `backend/app/config.py` | `0.45` | Boxes below this confidence are drawn as uncertain |
| `OBJECT_MIN_CONF` | `backend/app/config.py` | `0.5` | Stricter threshold for bags / objects (easily confused) |
| `STREAM_MAX_WIDTH` | `backend/app/config.py` | `960` | Frame width cap for inference and streaming |
| `JPEG_QUALITY` | `backend/app/config.py` | `72` | MJPEG quality |

Per-camera confidence, tracking, face, pose, PPE and model are changed live from the camera detail view.

## Project layout

```
backend/              FastAPI service
  app/camera.py         per-camera worker: capture, detect, track, pose, overlay
  app/rules.py          zones, line crossing, dwell, capacity
  app/pose.py · ppe.py  posture rules · helmet association
  app/media.py          alert snapshots and clips
  app/manager.py        camera registry, lifecycle, webhook
  app/auth.py           optional login and roles
  app/main.py           REST, MJPEG and WebSocket endpoints
  evaluate.py           metrics → Evaluation page
  train_ppe.py          fine-tune a helmet / PPE model
frontend/             React + TypeScript + Vite dashboard
  src/pages.tsx · extra.tsx   pages, alerts, evaluation, login
  src/components.tsx          camera tile, detail view, add-camera dialog
  src/ZoneEditor.tsx          zone and line editor
  src/charts.tsx              dependency-free SVG charts
Dockerfile · docker-compose.yml
docs/assets/          logo, banner and screenshots
```

## Known limitations

- **Overhead / top-down views are hard** for COCO-trained detectors, including the bundled Highway sample. Larger
  models help ([measurements](#models-and-performance)); fine-tuning on overhead data is the real fix.
- **FPS is shared** between cameras and drops as you add more. The Balanced model on a laptop gives about 3–5 FPS
  per camera with four cameras.
- **Unique counts** are per tracking session; people who are occluded or leave and re-enter can be counted twice.
- **PPE is not included**; see [Helmet / PPE](#helmet--ppe).
- **Fall detection** is a posture rule, not a trained activity model, and may raise false alarms.
- Evaluation numbers shipped here are a 4-image smoke test.
- Real webcam and RTSP camera support has not been exercised against physical hardware in this repository’s tests;
  the Docker image has not been build-tested on every platform.

## Privacy and responsible use

- Use footage only where you have the authority and permission to do so.
- Face detection locates faces; it does not identify anyone. Face recognition is intentionally not included.
- The system does not infer religion, ethnicity, identity, intent or suspiciousness from appearance or clothing.
- Restrict access to video and event records (turn on login), define retention and deletion, and keep a human in
  the loop for any consequential decision. Alert clips are stored on disk and capped at the newest 300 files.

## Roadmap

- [ ] Fine-tuned overhead / aerial vehicle detector
- [ ] Trained helmet / PPE model with evaluation on site footage
- [ ] Activity recognition (running, loading / unloading) with a temporal model
- [ ] Face-visibility (occluded / not visible) classification
- [ ] Batched multi-camera inference for higher FPS per camera
- [ ] Retention policies and audit log

## Credits

Built with [Ultralytics YOLO](https://github.com/ultralytics/ultralytics), [OpenCV](https://opencv.org/)
(YuNet face detector from [opencv_zoo](https://github.com/opencv/opencv_zoo)), [FastAPI](https://fastapi.tiangolo.com/),
[React](https://react.dev/) and [Lucide](https://lucide.dev/) icons. Demo clips are downloaded from
[intel-iot-devkit/sample-videos](https://github.com/intel-iot-devkit/sample-videos); refer to that repository for
their terms. Ultralytics YOLO is AGPL-3.0 licensed — review the license before commercial use.
