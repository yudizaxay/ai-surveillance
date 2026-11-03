import type { Camera, DetEvent, HealthInfo, HistoryPoint, Sample } from './types'

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
  streamUrl: (id: string) => `/api/cameras/${id}/stream`,
}
