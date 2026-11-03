import { useEffect, useState } from 'react'
import { Activity, LayoutDashboard, ListChecks, Plus, Server, WifiOff } from 'lucide-react'
import { AddCameraModal, ExpandedView } from './components'
import { AnalyticsPage, EventsPage, LivePage, SystemPage } from './pages'
import { useLive } from './useLive'

type View = 'live' | 'analytics' | 'events' | 'system'
const NAV: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: 'live', label: 'Live monitor', icon: <LayoutDashboard size={18} /> },
  { id: 'analytics', label: 'Analytics', icon: <Activity size={18} /> },
  { id: 'events', label: 'Events', icon: <ListChecks size={18} /> },
  { id: 'system', label: 'System', icon: <Server size={18} /> },
]
const VEHICLES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
const sumOf = (c: Record<string, number>, keys: string[]) => keys.reduce((a, k) => a + (c[k] ?? 0), 0)

const readView = (): View => {
  const h = location.hash.replace('#/', '') as View
  return NAV.some((n) => n.id === h) ? h : 'live'
}

export default function App() {
  const { cameras, summary, events, connected, loaded } = useLive()
  const [view, setView] = useState<View>(readView)
  const [cols, setCols] = useState<number>(() => Number(localStorage.getItem('cols')) || 0) // 0 = auto
  const [adding, setAdding] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [now, setNow] = useState(new Date())

  useEffect(() => { localStorage.setItem('cols', String(cols)) }, [cols])
  useEffect(() => {
    const on = () => setView(readView())
    window.addEventListener('hashchange', on)
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => { window.removeEventListener('hashchange', on); clearInterval(t) }
  }, [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  const go = (v: View) => { location.hash = `#/${v}` }
  const expanded = cameras.find((c) => c.id === expandedId)
  const title = NAV.find((n) => n.id === view)!.label

  return (
    <div className="shell">
      <nav className="rail">
        <a className="rail-brand" href="#/live" title="Vision Monitor">
          <img src="/logo.svg" alt="Vision Monitor" width={38} height={38} />
          <div><b>Vision</b><span>Monitor</span></div>
        </a>
        <div className="rail-nav">
          {NAV.map((n) => (
            <button key={n.id} className={view === n.id ? 'on' : ''} onClick={() => go(n.id)}>
              {n.icon}<span>{n.label}</span>
              {n.id === 'events' && events.length > 0 && <em>{events.length > 99 ? '99+' : events.length}</em>}
            </button>
          ))}
        </div>
        <div className="rail-foot">
          <div className={`conn ${connected ? 'ok' : 'bad'}`}>{connected ? <><i />Service connected</> : <><WifiOff size={14} />Reconnecting…</>}</div>
          <small>AI video analytics · PoC</small>
        </div>
      </nav>

      <div className="content">
        <header className="topbar">
          <h1>{title}</h1>
          <div className="kpis">
            <div className="kpi"><span>Cameras live</span><b>{summary.live}<small>/{summary.cameras}</small></b></div>
            <div className="kpi"><span>People now</span><b>{summary.current.person ?? 0}</b></div>
            <div className="kpi"><span>Unique people</span><b>{summary.unique.person ?? 0}</b></div>
            <div className="kpi"><span>Vehicles now</span><b>{sumOf(summary.current, VEHICLES)}</b></div>
            <div className="kpi"><span>Avg FPS</span><b>{summary.avg_fps}</b></div>
            <div className="kpi"><span>Latency</span><b>{summary.avg_latency_ms}<small>ms</small></b></div>
          </div>
          <div className="clock"><b>{now.toLocaleTimeString()}</b><span>{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}</span></div>
          <button className="primary" onClick={() => setAdding(true)}><Plus size={16} />Add camera</button>
        </header>

        <main className="view">
          {view === 'live' && (
            <LivePage cameras={cameras} summary={summary} events={events} loaded={loaded} cols={cols} setCols={setCols}
              onAdd={() => setAdding(true)} onExpand={setExpandedId} onError={setToast} />
          )}
          {view === 'analytics' && <AnalyticsPage cameras={cameras} summary={summary} />}
          {view === 'events' && <EventsPage events={events} cameras={cameras} />}
          {view === 'system' && <SystemPage cameras={cameras} />}
        </main>
      </div>

      {adding && <AddCameraModal onClose={() => setAdding(false)} onAdded={() => {}} onError={setToast} />}
      {expanded && <ExpandedView cam={expanded} onClose={() => setExpandedId(null)} onError={setToast} />}
      {toast && <div className="toast" onClick={() => setToast(null)}>{toast}</div>}
    </div>
  )
}
