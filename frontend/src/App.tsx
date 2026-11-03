import { useCallback, useEffect, useRef, useState } from 'react'
import { Activity, BellRing, FlaskConical, LayoutDashboard, ListChecks, LogOut, Plus, Server, WifiOff } from 'lucide-react'
import { api } from './api'
import { AddCameraModal, ExpandedView } from './components'
import { AlertToast, AlertsPage, EvalPage, LoginScreen, beep } from './extra'
import { AnalyticsPage, EventsPage, LivePage, SystemPage } from './pages'
import type { AuthState, DetEvent } from './types'
import { useLive } from './useLive'
import { ZoneEditor } from './ZoneEditor'

type View = 'live' | 'alerts' | 'analytics' | 'events' | 'evaluation' | 'system'
const NAV: { id: View; label: string; icon: React.ReactNode }[] = [
  { id: 'live', label: 'Live monitor', icon: <LayoutDashboard size={18} /> },
  { id: 'alerts', label: 'Alerts', icon: <BellRing size={18} /> },
  { id: 'analytics', label: 'Analytics', icon: <Activity size={18} /> },
  { id: 'events', label: 'Events', icon: <ListChecks size={18} /> },
  { id: 'evaluation', label: 'Evaluation', icon: <FlaskConical size={18} /> },
  { id: 'system', label: 'System', icon: <Server size={18} /> },
]
const VEHICLES = ['car', 'truck', 'bus', 'motorcycle', 'bicycle']
const sumOf = (c: Record<string, number>, keys: string[]) => keys.reduce((a, k) => a + (c[k] ?? 0), 0)

const readView = (): View => {
  const h = location.hash.replace('#/', '') as View
  return NAV.some((n) => n.id === h) ? h : 'live'
}

export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(null)
  const refreshAuth = useCallback(() => { api.me().then(setAuth).catch(() => setAuth({ required: false, user: null, role: 'admin' })) }, [])
  useEffect(refreshAuth, [refreshAuth])

  if (auth === null) return <div className="login"><div className="spinner" /></div>
  if (auth.required && !auth.user) return <LoginScreen onDone={setAuth} />
  return <Dashboard auth={auth} onAuthLost={refreshAuth} onLogout={() => { api.logout().finally(refreshAuth) }} />
}

function Dashboard({ auth, onAuthLost, onLogout }: { auth: AuthState; onAuthLost: () => void; onLogout: () => void }) {
  const { cameras, summary, events, connected, loaded, alertsUnacked } = useLive(true, onAuthLost)
  const readOnly = auth.role === 'viewer'
  const [view, setView] = useState<View>(readView)
  const [cols, setCols] = useState<number>(() => Number(localStorage.getItem('cols')) || 0) // 0 = auto
  const [muted, setMutedState] = useState<boolean>(() => localStorage.getItem('muted') === '1')
  const [adding, setAdding] = useState(false)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [zonesId, setZonesId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [alertToast, setAlertToast] = useState<DetEvent | null>(null)
  const [now, setNow] = useState(new Date())
  const startTs = useRef(Date.now() / 1000 - 1)
  const lastToast = useRef(0)

  const setMuted = (m: boolean) => { setMutedState(m); try { localStorage.setItem('muted', m ? '1' : '0') } catch { /* ignore */ } }
  useEffect(() => { try { localStorage.setItem('cols', String(cols)) } catch { /* ignore */ } }, [cols])
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

  // pop a banner (and a beep) for each new alert that arrives while the dashboard is open
  useEffect(() => {
    const fresh = events.find((e) => e.severity === 'alert' && e.id > lastToast.current && e.ts >= startTs.current)
    if (!fresh) return
    lastToast.current = fresh.id
    setAlertToast(fresh)
    if (!muted) beep()
  }, [events, muted])

  const go = (v: View) => { location.hash = `#/${v}` }
  const expanded = cameras.find((c) => c.id === expandedId)
  const zoneCam = cameras.find((c) => c.id === zonesId)
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
              {n.id === 'alerts' && alertsUnacked > 0 && <em className="hot">{alertsUnacked > 99 ? '99+' : alertsUnacked}</em>}
            </button>
          ))}
        </div>
        <div className="rail-foot">
          {auth.required && (
            <div className="whoami"><span>{auth.user}<small>{auth.role}</small></span>
              <button className="icon" title="Sign out" onClick={onLogout}><LogOut size={15} /></button></div>
          )}
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
            <div className={`kpi ${alertsUnacked ? 'kpi-alert' : ''}`}><span>Open alerts</span><b>{alertsUnacked}</b></div>
            <div className="kpi"><span>Avg FPS</span><b>{summary.avg_fps}</b></div>
            <div className="kpi"><span>Latency</span><b>{summary.avg_latency_ms}<small>ms</small></b></div>
          </div>
          <div className="clock"><b>{now.toLocaleTimeString()}</b><span>{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}</span></div>
          {!readOnly && <button className="primary" onClick={() => setAdding(true)}><Plus size={16} />Add camera</button>}
        </header>

        <main className="view">
          {view === 'live' && (
            <LivePage cameras={cameras} summary={summary} events={events} loaded={loaded} cols={cols} setCols={setCols}
              onAdd={() => setAdding(true)} onExpand={setExpandedId} onError={setToast} readOnly={readOnly} />
          )}
          {view === 'alerts' && <AlertsPage live={events} cameras={cameras} readOnly={readOnly} muted={muted} setMuted={setMuted} />}
          {view === 'analytics' && <AnalyticsPage cameras={cameras} summary={summary} />}
          {view === 'events' && <EventsPage events={events} cameras={cameras} />}
          {view === 'evaluation' && <EvalPage />}
          {view === 'system' && <SystemPage cameras={cameras} readOnly={readOnly} />}
        </main>
      </div>

      {adding && <AddCameraModal onClose={() => setAdding(false)} onAdded={() => {}} onError={setToast} />}
      {expanded && !zoneCam && (
        <ExpandedView cam={expanded} onClose={() => setExpandedId(null)} onError={setToast} readOnly={readOnly}
          onEditZones={() => setZonesId(expanded.id)} />
      )}
      {zoneCam && <ZoneEditor cam={zoneCam} readOnly={readOnly} onClose={() => setZonesId(null)} onError={setToast} />}
      {alertToast && view !== 'alerts' && <AlertToast ev={alertToast} onClose={() => setAlertToast(null)} />}
      {toast && <div className="toast" onClick={() => setToast(null)}>{toast}</div>}
    </div>
  )
}
