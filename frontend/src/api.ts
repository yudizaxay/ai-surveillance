import type { AuthState, Camera, DetectorInfo, DetEvent, EvalResult, HealthInfo, HistoryPoint, Sample } from './types'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText
    try {
      const body = await res.json()
      msg = body.detail || msg
    } catch { /* ignore */ }
    throw new Error(msg)
  }
  return res.json()
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  addCamera: (b: { name: string; kind: string; source: string; faces?: boolean }) =>
    fetch('/api/cameras', json('POST', b)).then(j<Camera>),
  upload: (file: File, name: string) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('name', name)
    return fetch('/api/cameras/upload', { method: 'POST', body: fd }).then(j<Camera>)
  },
  remove: (id: string) => fetch(`/api/cameras/${id}`, { method: 'DELETE' }).then(j<unknown>),
  start: (id: string) => fetch(`/api/cameras/${id}/start`, { method: 'POST' }).then(j<Camera>),
  stop: (id: string) => fetch(`/api/cameras/${id}/stop`, { method: 'POST' }).then(j<unknown>),
  patch: (id: string, p: Record<string, unknown>) =>
    fetch(`/api/cameras/${id}`, json('PATCH', p)).then(j<Camera>),
  discover: () => fetch('/api/discover').then(j<{ index: number; in_use: boolean }[]>),
  samples: () => fetch('/api/samples').then(j<Sample[]>),
  events: (limit = 60) => fetch(`/api/events?limit=${limit}`).then(j<DetEvent[]>),
  history: (minutes = 15) => fetch(`/api/history?minutes=${minutes}`).then(j<HistoryPoint[]>),
  health: () => fetch('/api/health').then(j<HealthInfo>),
  alerts: (limit = 200) => fetch(`/api/alerts?limit=${limit}`).then(j<DetEvent[]>),
  ack: (b: { id?: number; all?: boolean }) => fetch('/api/alerts/ack', json('POST', b)).then(j<unknown>),
  webhook: () => fetch('/api/settings/webhook').then(j<{ configured: boolean; host: string | null }>),
  setWebhook: (url: string) => fetch('/api/settings/webhook', json('PUT', { url })).then(j<{ configured: boolean; host: string | null }>),
  testWebhook: () => fetch('/api/settings/webhook/test', { method: 'POST' }).then(j<unknown>),
  detector: () => fetch('/api/settings/detector').then(j<DetectorInfo>),
  setDetector: (file: string) => fetch('/api/settings/detector', json('PUT', { file })).then(j<DetectorInfo>),
  evals: () => fetch('/api/eval').then(j<EvalResult[]>),
  me: () => fetch('/api/auth/me').then(j<AuthState>),
  login: (username: string, password: string) => fetch('/api/auth/login', json('POST', { username, password })).then(j<AuthState>),
  logout: () => fetch('/api/auth/logout', { method: 'POST' }).then(j<unknown>),
  resetHeat: (id: string) => fetch(`/api/cameras/${id}/heatmap/reset`, { method: 'POST' }).then(j<unknown>),
  mediaUrl: (name: string) => `/api/media/${name}`,
  snapshotUrl: (id: string) => `/api/cameras/${id}/snapshot`,
  heatmapUrl: (id: string) => `/api/cameras/${id}/heatmap`,
  streamUrl: (id: string) => `/api/cameras/${id}/stream`,
}
