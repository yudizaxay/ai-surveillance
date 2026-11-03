import { useEffect, useMemo, useState } from 'react'
import { Download, LayoutGrid, Plus, Search } from 'lucide-react'
import { api } from './api'
import { Donut, LineChart } from './charts'
import { AboutPanel, CameraTile, CAT_COLORS, EventFeed, StatusBadge, TotalsPanel } from './components'
import type { Camera, DetEvent, HealthInfo, HistoryPoint, Summary } from './types'

const VEHICLES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
const sumOf = (c: Record<string, number> | undefined, keys: string[]) => keys.reduce((a, k) => a + (c?.[k] ?? 0), 0)
const CAT_NAME: Record<string, string> = {
  person: 'People', car: 'Cars', truck: 'Trucks', bus: 'Buses', motorcycle: 'Motorcycles',
  bicycle: 'Bicycles', animal: 'Animals', object: 'Bags',
}

/* ------------------------------------------------------------------ LIVE */
export function LivePage({
  cameras, summary, events, loaded, cols, setCols, onAdd, onExpand, onError,
}: {
  cameras: Camera[]; summary: Summary; events: DetEvent[]; loaded: boolean
  cols: number; setCols: (n: number) => void; onAdd: () => void; onExpand: (id: string) => void; onError: (m: string) => void
}) {
  const auto = cameras.length <= 1 ? 1 : cameras.length <= 4 ? 2 : 3
  const grid = cols || auto
  return (
    <div className="split">
      <section className="stage">
        <div className="toolbar">
          <h2>Live cameras <span className="count">{summary.live}/{cameras.length} online</span></h2>
          <div className="spacer" />
          <div className="seg" title="Grid columns">
            <LayoutGrid size={14} />
            {[0, 1, 2, 3, 4].map((n) => (
              <button key={n} className={cols === n ? 'on' : ''} onClick={() => setCols(n)}>{n === 0 ? 'Auto' : n}</button>
            ))}
          </div>
        </div>
        {!loaded && <div className="empty"><div className="spinner" />Connecting to analytics service…</div>}
        {loaded && cameras.length === 0 && (
          <div className="empty">
            <img src="/logo.svg" width={56} height={56} alt="" />
            <h3>No cameras connected</h3>
            <p>Add a webcam, sample video, uploaded clip or RTSP stream to start live detection.</p>
            <button className="primary" onClick={onAdd}><Plus size={16} />Add your first camera</button>
          </div>
        )}
        <div className="grid" style={{ gridTemplateColumns: `repeat(${grid}, minmax(0, 1fr))` }}>
          {cameras.map((c) => <CameraTile key={c.id} cam={c} onExpand={() => onExpand(c.id)} onError={onError} />)}
        </div>
      </section>
      <aside className="side">
        <TotalsPanel s={summary} />
        <EventFeed events={events} />
      </aside>
    </div>
  )
}

/* ------------------------------------------------------------- ANALYTICS */
export function AnalyticsPage({ cameras, summary }: { cameras: Camera[]; summary: Summary }) {
  const [minutes, setMinutes] = useState(15)
  const [hist, setHist] = useState<HistoryPoint[]>([])
  useEffect(() => {
    let live = true
    const load = () => api.history(minutes).then((h) => live && setHist(h)).catch(() => {})
    load()
    const t = setInterval(load, 5000)
    return () => { live = false; clearInterval(t) }
  }, [minutes])

  const times = hist.map((h) => h.ts)
  const peakPeople = Math.max(0, ...hist.map((h) => h.current.person ?? 0))
  const peakVeh = Math.max(0, ...hist.map((h) => sumOf(h.current, VEHICLES)))
  const parts = Object.keys(CAT_NAME).map((k) => ({ name: CAT_NAME[k], value: summary.unique[k] ?? 0, color: CAT_COLORS[k] }))

  return (
    <div className="page">
      <div className="toolbar">
        <h2>Analytics</h2><div className="spacer" />
        <div className="seg">
          {[5, 15, 30, 60].map((m) => <button key={m} className={minutes === m ? 'on' : ''} onClick={() => setMinutes(m)}>{m}m</button>)}
        </div>
      </div>

      <div className="cards">
        <div className="card"><span>Unique people</span><b>{summary.unique.person ?? 0}</b><small>distinct track IDs, all cameras</small></div>
        <div className="card"><span>Unique vehicles</span><b>{sumOf(summary.unique, VEHICLES)}</b><small>cars, trucks, buses, bikes</small></div>
        <div className="card"><span>Peak people in view</span><b>{peakPeople}</b><small>last {minutes} min</small></div>
        <div className="card"><span>Peak vehicles in view</span><b>{peakVeh}</b><small>last {minutes} min</small></div>
        <div className="card"><span>Avg FPS</span><b>{summary.avg_fps}</b><small>per live camera</small></div>
        <div className="card"><span>Avg latency</span><b>{summary.avg_latency_ms}<em>ms</em></b><small>inference per frame</small></div>
      </div>

      <div className="two">
        <section className="panel">
          <div className="panel-head"><h3>Objects in view</h3><span className="muted">sum across live cameras</span></div>
          <LineChart times={times} series={[
            { name: 'People', color: CAT_COLORS.person, values: hist.map((h) => h.current.person ?? 0) },
            { name: 'Vehicles', color: CAT_COLORS.car, values: hist.map((h) => sumOf(h.current, VEHICLES)) },
            { name: 'Animals', color: CAT_COLORS.animal, values: hist.map((h) => h.current.animal ?? 0) },
          ]} />
        </section>
        <section className="panel">
          <div className="panel-head"><h3>Unique tracked by class</h3><span className="muted">since stream start</span></div>
          <Donut parts={parts} />
        </section>
      </div>

      <div className="two">
        <section className="panel">
          <div className="panel-head"><h3>Throughput</h3><span className="muted">avg FPS</span></div>
          <LineChart times={times} series={[{ name: 'FPS', color: '#3dd6c6', values: hist.map((h) => Math.round(h.fps * 10) / 10) }]} />
        </section>
        <section className="panel">
          <div className="panel-head"><h3>Inference latency</h3><span className="muted">ms per frame (warm-up spikes clipped at 600)</span></div>
          <LineChart unit=" ms" times={times} series={[{ name: 'Latency', color: '#ffb020', values: hist.map((h) => Math.min(Math.round(h.latency_ms), 600)) }]} />
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><h3>Per-camera breakdown</h3></div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Camera</th><th>Status</th><th>People now</th><th>Unique people</th><th>Vehicles now</th><th>Unique vehicles</th><th>Animals</th><th>FPS</th><th>Latency</th></tr></thead>
            <tbody>
              {cameras.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td><td><StatusBadge status={c.status} /></td>
                  <td>{c.current.person}</td><td>{c.unique.person}</td>
                  <td>{sumOf(c.current, VEHICLES)}</td><td>{sumOf(c.unique, VEHICLES)}</td>
                  <td>{c.unique.animal}</td><td>{c.fps.toFixed(1)}</td><td>{Math.round(c.latency_ms)} ms</td>
                </tr>
              ))}
              {cameras.length === 0 && <tr><td colSpan={9} className="muted">No cameras</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="note">“Unique” counts distinct ByteTrack IDs per tracking session; people who leave and re-enter, or are occluded, can be counted more than once.</p>
      </section>
    </div>
  )
}

/* ---------------------------------------------------------------- EVENTS */
const TYPE_LABEL: Record<string, string> = {
  new_track: 'Detection', camera_online: 'Camera online', camera_offline: 'Camera offline', camera_error: 'Camera error',
}

export function EventsPage({ events, cameras }: { events: DetEvent[]; cameras: Camera[] }) {
  const [all, setAll] = useState<DetEvent[]>([])
  const [cam, setCam] = useState('')
  const [type, setType] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => { api.events(500).then(setAll).catch(() => {}) }, [])

  // merge the live feed (newest first) with the loaded history, de-duplicated by id
  const merged = useMemo(() => {
    const seen = new Set<number>()
    return [...events, ...all].filter((e) => !seen.has(e.id) && seen.add(e.id)).sort((a, b) => b.id - a.id)
  }, [events, all])

  const rows = merged.filter((e) =>
    (!cam || e.camera_id === cam) && (!type || e.type === type) &&
    (!q || `${e.message} ${e.label} ${e.camera_name}`.toLowerCase().includes(q.toLowerCase())))

  return (
    <div className="page">
      <div className="toolbar">
        <h2>Events <span className="count">{rows.length}</span></h2><div className="spacer" />
        <label className="search"><Search size={14} /><input placeholder="Search events" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <select value={cam} onChange={(e) => setCam(e.target.value)}>
          <option value="">All cameras</option>
          {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All types</option>
          {Object.entries(TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <a className="primary" href="/api/report.csv"><Download size={15} />Export CSV</a>
      </div>
      <section className="panel">
        <div className="table-wrap tall">
          <table className="data">
            <thead><tr><th>Time</th><th>Camera</th><th>Type</th><th>Detail</th><th>Track</th><th>Confidence</th></tr></thead>
            <tbody>
              {rows.slice(0, 300).map((e) => (
                <tr key={e.id}>
                  <td className="mono">{new Date(e.ts * 1000).toLocaleString()}</td>
                  <td>{e.camera_name}</td>
                  <td><span className={`tag tag-${e.type}`}>{TYPE_LABEL[e.type] ?? e.type}</span></td>
                  <td>{e.message}</td>
                  <td className="mono">{e.track_id != null ? `#${e.track_id}` : '—'}</td>
                  <td className="mono">{e.confidence != null ? `${Math.round(e.confidence * 100)}%` : '—'}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan={6} className="muted">No events match</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

/* ---------------------------------------------------------------- SYSTEM */
export function SystemPage({ cameras }: { cameras: Camera[] }) {
  const [h, setH] = useState<HealthInfo | null>(null)
  useEffect(() => {
    const load = () => api.health().then(setH).catch(() => setH(null))
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])
  const up = h ? `${Math.floor(h.uptime / 3600)}h ${Math.floor((h.uptime % 3600) / 60)}m` : '—'
  return (
    <div className="page">
      <div className="toolbar"><h2>System</h2></div>
      <div className="cards">
        <div className="card"><span>Service</span><b className={h ? 'ok' : 'bad'}>{h ? 'Online' : 'Offline'}</b><small>uptime {up}</small></div>
        <div className="card"><span>Inference device</span><b>{h?.device ?? '—'}</b><small>mps = Apple GPU · cuda = NVIDIA</small></div>
        <div className="card"><span>Object model</span><b className="small">{h?.model ?? '—'}</b><small>COCO pre-trained</small></div>
        <div className="card"><span>Face model</span><b className="small">{h?.face_model ?? 'not loaded'}</b><small>detection only</small></div>
        <div className="card"><span>Tracker</span><b className="small">{h?.tracker ?? '—'}</b><small>persistent track IDs</small></div>
        <div className="card"><span>Cameras</span><b>{cameras.length}</b><small>{cameras.filter((c) => c.status === 'live').length} live</small></div>
      </div>
      <div className="two">
        <section className="panel">
          <div className="panel-head"><h3>Capabilities</h3></div>
          <table className="data">
            <thead><tr><th>Capability</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>Person, vehicles, animals, bags</td><td><span className="tag tag-ok">Pre-trained</span></td></tr>
              <tr><td>Multi-object tracking &amp; unique counts</td><td><span className="tag tag-ok">Pre-trained</span></td></tr>
              <tr><td>Face detection (no identification)</td><td><span className="tag tag-ok">Pre-trained</span></td></tr>
              <tr><td>Helmet / PPE detection</td><td><span className="tag tag-todo">Needs custom model</span></td></tr>
              <tr><td>Pose &amp; activity recognition</td><td><span className="tag tag-todo">Roadmap</span></td></tr>
              <tr><td>Zones &amp; line crossing</td><td><span className="tag tag-todo">Roadmap</span></td></tr>
            </tbody>
          </table>
        </section>
        <AboutPanel />
      </div>
      <section className="panel">
        <div className="panel-head"><h3>Camera runtime</h3></div>
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Camera</th><th>Source</th><th>Status</th><th>Resolution</th><th>Frames</th><th>FPS</th><th>Latency</th><th>Loops</th></tr></thead>
            <tbody>
              {cameras.map((c) => (
                <tr key={c.id}><td>{c.name}</td><td>{c.kind}</td><td><StatusBadge status={c.status} /></td><td className="mono">{c.resolution || '—'}</td>
                  <td className="mono">{c.frames.toLocaleString()}</td><td>{c.fps.toFixed(1)}</td><td>{Math.round(c.latency_ms)} ms</td><td>{c.kind === 'file' ? c.loops : '—'}</td></tr>
              ))}
              {cameras.length === 0 && <tr><td colSpan={8} className="muted">No cameras</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

