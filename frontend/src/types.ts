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
  settings: { conf: number; faces: boolean; tracking: boolean }
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
}
