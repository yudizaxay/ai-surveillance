import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { Camera, DetEvent, Summary } from './types'

const EMPTY: Summary = {
  cameras: 0, live: 0, errors: 0, current: {}, unique: {}, avg_fps: 0, avg_latency_ms: 0,
}

/** Live stats + events from the backend WebSocket, with automatic reconnect. */
export function useLive() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [summary, setSummary] = useState<Summary>(EMPTY)
  const [events, setEvents] = useState<DetEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const retry = useRef(0)

  useEffect(() => {
    api.events(60).then(setEvents).catch(() => {})
  }, [])

  useEffect(() => {
    let ws: WebSocket | null = null
    let timer: number | undefined
    let closed = false

    const open = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws`)
      ws.onopen = () => { retry.current = 0; setConnected(true) }
      ws.onmessage = (m) => {
        const msg = JSON.parse(m.data)
        if (msg.type === 'stats') {
          setCameras(msg.cameras)
          setSummary(msg.summary)
          setLoaded(true)
        } else if (msg.type === 'event') {
          setEvents((prev) => [msg.event, ...prev].slice(0, 80))
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (closed) return
        retry.current += 1
        timer = window.setTimeout(open, Math.min(1000 * retry.current, 5000))
      }
      ws.onerror = () => ws?.close()
    }
    open()
    return () => { closed = true; clearTimeout(timer); ws?.close() }
  }, [])

  return { cameras, summary, events, connected, loaded }
}
