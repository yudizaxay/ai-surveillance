import { useEffect, useState } from 'react'
import { Eye, LayoutGrid, Plus, WifiOff } from 'lucide-react'
import { AboutPanel, AddCameraModal, CameraTile, EventFeed, ExpandedView, TotalsPanel } from './components'
import { useLive } from './useLive'

const sumOf = (c: Record<string, number>, keys: string[]) => keys.reduce((a, k) => a + (c[k] ?? 0), 0)
const VEHICLES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']

export default function App() {
  const { cameras, summary, events, connected, loaded } = useLive()
  const [cols, setCols] = useState<number>(() => Number(localStorage.getItem('cols')) || 0) // 0 = auto
  const [adding, setAdding] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => { localStorage.setItem('cols', String(cols)) }, [cols])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  const expanded = cameras.find((c) => c.id === expandedId)
  const auto = cameras.length <= 1 ? 1 : cameras.length <= 4 ? 2 : 3
  const grid = cols || auto

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><Eye size={20} /><div><h1>Vision Monitor</h1><span>AI video analytics · proof of concept</span></div></div>
        <div className="kpis">
          <div className="kpi"><span>Cameras live</span><b>{summary.live}<small>/{summary.cameras}</small></b></div>
          <div className="kpi"><span>People now</span><b>{summary.current.person ?? 0}</b></div>
          <div className="kpi"><span>Unique people</span><b>{summary.unique.person ?? 0}</b></div>
          <div className="kpi"><span>Vehicles now</span><b>{sumOf(summary.current, VEHICLES)}</b></div>
          <div className="kpi"><span>Avg FPS</span><b>{summary.avg_fps}</b></div>
          <div className="kpi"><span>Avg latency</span><b>{summary.avg_latency_ms}<small>ms</small></b></div>
        </div>
        <div className={`conn ${connected ? 'ok' : 'bad'}`}>{connected ? <><i />Connected</> : <><WifiOff size={14} />Reconnecting…</>}</div>
      </header>

      <main className="layout">
        <section className="stage">
          <div className="toolbar">
            <h2>Cameras <span className="count">{cameras.length}</span></h2>
            <div className="spacer" />
            <div className="seg" title="Grid columns">
              <LayoutGrid size={14} />
              {[0, 1, 2, 3, 4].map((n) => (
                <button key={n} className={cols === n ? 'on' : ''} onClick={() => setCols(n)}>{n === 0 ? 'Auto' : n}</button>
              ))}
            </div>
            <button className="primary" onClick={() => setAdding(true)}><Plus size={16} />Add camera</button>
          </div>

          {!loaded && <div className="empty"><div className="spinner" />Connecting to analytics service…</div>}
          {loaded && cameras.length === 0 && (
            <div className="empty">
              <Eye size={34} />
              <h3>No cameras connected</h3>
              <p>Add a webcam, sample video, uploaded clip or RTSP stream to start live detection.</p>
              <button className="primary" onClick={() => setAdding(true)}><Plus size={16} />Add your first camera</button>
            </div>
          )}
          <div className="grid" style={{ gridTemplateColumns: `repeat(${grid}, minmax(0, 1fr))` }}>
            {cameras.map((c) => (
              <CameraTile key={c.id} cam={c} onExpand={() => setExpandedId(c.id)} onError={setToast} />
            ))}
          </div>
        </section>

        <aside className="side">
          <TotalsPanel s={summary} />
          <EventFeed events={events} />
          <AboutPanel />
        </aside>
      </main>

      {adding && <AddCameraModal onClose={() => setAdding(false)} onAdded={() => {}} onError={setToast} />}
      {expanded && <ExpandedView cam={expanded} onClose={() => setExpandedId(null)} onError={setToast} />}
      {toast && <div className="toast" onClick={() => setToast(null)}>{toast}</div>}
    </div>
  )
}
