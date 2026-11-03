export type Counts = Record<string, number>

export interface Camera {
  id: string
  name: string
  kind: 'webcam' | 'file' | 'rtsp'
  status: 'starting' | 'live' | 'error' | 'stopped'
  error: string | null
  fps: number
  latency_ms: number
  resolution: string
  settings: {
    conf: number; faces: boolean; tracking: boolean; pose: boolean; ppe: boolean
    zones: Zone[]; lines: Line[]; model: string
  }
  model: string
  rules: { zones: Record<string, { occupancy: number; entries: number }>; lines: Record<string, { in: number; out: number }> }
  postures: Record<string, number>
  ppe: { helmet_yes: number; helmet_no: number; helmet_unknown: number }
  features: { pose_available: boolean; pose_error: string | null; ppe_available: boolean; ppe_error: string | null }
  current: Counts
  unique: Counts
  detections_total: number
  frames: number
  uptime: number
  loops: number
  device: string
}

export interface Summary {
  cameras: number
  live: number
  errors: number
  current: Counts
  unique: Counts
  avg_fps: number
  avg_latency_ms: number
}

export interface DetEvent {
  id: number
  ts: number
  camera_id: string
  camera_name: string
  type: string
  label?: string | null
  track_id?: number | null
  confidence?: number | null
  message?: string | null
  severity?: 'info' | 'alert'
  ack?: number
  image?: string | null
  clip?: string | null
  zone?: string | null
}

export interface Sample {
  file: string
  name: string
}

export interface HistoryPoint {
  ts: number
  live: number
  current: Counts
  unique: Counts
  fps: number
  latency_ms: number
}

export interface HealthInfo {
  ok: boolean
  device: string
  model: string
  face_model: string | null
  tracker: string
  uptime: number
  pose_model?: string | null
  ppe_model?: string | null
  auth?: boolean
}

export type Pt = [number, number]

export interface Zone {
  id: string
  name: string
  points: Pt[]
  classes: string[]
  color: string
  alert_on_enter: boolean
  dwell_s: number
  max_occupancy: number
  require_helmet: boolean
}

export interface Line {
  id: string
  name: string
  p1: Pt
  p2: Pt
  classes: string[]
  alert: boolean
}

export interface EvalResult {
  name: string
  weights: string
  dataset: string
  images: number | null
  conf_threshold: number
  iou_threshold: number
  imgsz: number
  device: string
  ts: number
  overall: { precision: number; recall: number; f1: number | null; map50: number; map50_95: number }
  speed_ms: Record<string, number>
  per_class: { class: string; precision: number; recall: number; f1: number; map50: number; map50_95: number; instances: number | null }[]
  note: string
}

export interface AuthState {
  required: boolean
  user: string | null
  role: 'admin' | 'viewer' | null
}

export interface DetectorInfo {
  current: string
  options: { file: string; label: string; hint: string; installed: boolean }[]
}
