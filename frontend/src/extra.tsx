import { useEffect, useMemo, useState } from 'react'
import { Bell, BellOff, Check, CheckCheck, Clapperboard, Lock, ShieldAlert, X } from 'lucide-react'
import { api } from './api'
import type { AuthState, Camera, DetEvent, EvalResult } from './types'

/* ----------------------------------------------------------------- sound */
let audio: AudioContext | null = null
export function beep() {
  try {
    audio = audio ?? new AudioContext()
    const o = audio.createOscillator(), g = audio.createGain()
    o.type = 'sine'; o.frequency.value = 880
    g.gain.setValueAtTime(0.0001, audio.currentTime)
    g.gain.exponentialRampToValueAtTime(0.15, audio.currentTime + 0.02)
    g.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + 0.35)
    o.connect(g).connect(audio.destination); o.start(); o.stop(audio.currentTime + 0.4)
  } catch { /* audio blocked until the user interacts with the page */ }
}

const TYPE_LABEL: Record<string, string> = {
  line_cross: 'Line crossed', zone_enter: 'Zone entry', dwell: 'Dwell time', capacity: 'Over capacity',
  fall: 'Possible fall', ppe_violation: 'No helmet', visibility: 'Low visibility', visibility_clear: 'Visibility restored', camera_error: 'Camera error',
}
export const alertLabel = (t: string) => TYPE_LABEL[t] ?? t

/* ----------------------------------------------------------- alert toast */
export function AlertToast({ ev, onClose }: { ev: DetEvent; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 8000); return () => clearTimeout(t) }, [ev.id, onClose])
  return (
    <a className="alert-toast" href="#/alerts" onClick={onClose}>
      <ShieldAlert size={20} />
      <div><b>{alertLabel(ev.type)}</b><span>{ev.message}</span><small>{ev.camera_name}</small></div>
      <button className="icon" onClick={(e) => { e.preventDefault(); e.stopPropagation(); onClose() }}><X size={16} /></button>
    </a>
  )
}

/* ---------------------------------------------------------------- alerts */
export function AlertsPage({ live, cameras, readOnly, muted, setMuted }: {
  live: DetEvent[]; cameras: Camera[]; readOnly: boolean; muted: boolean; setMuted: (m: boolean) => void
}) {
  const [stored, setStored] = useState<DetEvent[]>([])
  const [onlyNew, setOnlyNew] = useState(false)
  const [cam, setCam] = useState('')
  const [view, setView] = useState<DetEvent | null>(null)
  const [acked, setAcked] = useState<Set<number>>(new Set())
  const load = () => api.alerts(300).then(setStored).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t) }, [])

  const rows = useMemo(() => {
    const seen = new Set<number>()
    const liveAlerts = live.filter((e) => e.severity === 'alert')
    return [...liveAlerts, ...stored].filter((e) => !seen.has(e.id) && seen.add(e.id)).sort((a, b) => b.id - a.id)
  }, [live, stored])
  const isAcked = (e: DetEvent) => !!e.ack || acked.has(e.id)
  const shown = rows.filter((e) => (!cam || e.camera_id === cam) && (!onlyNew || !isAcked(e)))
  const unacked = rows.filter((e) => !isAcked(e)).length

  const ack = async (e: DetEvent) => { await api.ack({ id: e.id }).catch(() => {}); setAcked((s) => new Set(s).add(e.id)); load() }
  const ackAll = async () => { await api.ack({ all: true }).catch(() => {}); setAcked(new Set(rows.map((r) => r.id))); load() }

  return (
    <div className="page">
      <div className="toolbar">
        <h2>Alerts <span className={`count ${unacked ? 'hot' : ''}`}>{unacked} new</span></h2><div className="spacer" />
        <button className="ghost" onClick={() => setMuted(!muted)} title="Alert sound">{muted ? <BellOff size={15} /> : <Bell size={15} />}{muted ? 'Sound off' : 'Sound on'}</button>
        <label className="toggle inline"><input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} />Unacknowledged only</label>
        <select value={cam} onChange={(e) => setCam(e.target.value)}>
          <option value="">All cameras</option>
          {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {!readOnly && <button className="primary" disabled={!unacked} onClick={ackAll}><CheckCheck size={15} />Acknowledge all</button>}
      </div>

      {shown.length === 0 && (
        <div className="empty"><ShieldAlert size={30} /><h3>No alerts</h3>
          <p>Alerts are raised by zone / line rules, dwell and capacity limits, possible falls, missing helmets and camera failures. Draw zones from a camera’s expanded view.</p></div>
      )}
      <div className="alert-list">
        {shown.slice(0, 100).map((e) => (
          <article key={e.id} className={`alert-card ${isAcked(e) ? 'done' : ''}`}>
            <div className="alert-thumb" onClick={() => e.image && setView(e)}>
              {e.image ? <img src={api.mediaUrl(e.image)} alt="" loading="lazy" /> : <ShieldAlert size={26} />}
              {e.clip && <span className="play"><Clapperboard size={13} />clip</span>}
            </div>
            <div className="alert-body">
              <div className="alert-top"><span className={`tag tag-${e.type}`}>{alertLabel(e.type)}</span>
                <time>{new Date(e.ts * 1000).toLocaleString()}</time></div>
              <p>{e.message}</p>
              <small>{e.camera_name}{e.zone ? ` · ${e.zone}` : ''}{e.track_id != null ? ` · track #${e.track_id}` : ''}</small>
              <div className="alert-actions">
                {(e.image || e.clip) && <button className="ghost" onClick={() => setView(e)}>Review</button>}
                {!readOnly && (isAcked(e)
                  ? <span className="muted"><Check size={13} /> acknowledged</span>
                  : <button className="ghost" onClick={() => ack(e)}><Check size={13} />Acknowledge</button>)}
              </div>
            </div>
          </article>
        ))}
      </div>
      <p className="note">Alerts are prompts for a person to look, not conclusions. Possible-fall and no-helmet alerts can be wrong; review the clip before acting.</p>

      {view && (
        <div className="overlay" onClick={() => setView(null)}>
          <div className="modal media-modal" onClick={(e) => e.stopPropagation()}>
            <header><h2>{alertLabel(view.type)}</h2><button className="icon" onClick={() => setView(null)}><X size={18} /></button></header>
            <ClipPlayer ev={view} />
            <p>{view.message}</p>
            <small className="muted">{view.camera_name} · {new Date(view.ts * 1000).toLocaleString()}</small>
          </div>
        </div>
      )}
    </div>
  )
}

function ClipPlayer({ ev }: { ev: DetEvent }) {
  // A clip is written a few seconds after the alert (it includes the footage that follows), so a brand-new
  // alert may 404 at first: show the snapshot and retry for ~30 s before giving up.
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')
  useEffect(() => {
    if (state !== 'loading' || !ev.clip) return
    const t = setTimeout(() => setAttempt((n) => n + 1), 3000)
    return () => clearTimeout(t)
  }, [state, attempt, ev.clip])
  const onError = () => { if (attempt >= 10) setState('failed'); else setTimeout(() => setAttempt((n) => n + 1), 3000) }
  if (ev.clip && state !== 'failed') {
    return (
      <>
        <video key={attempt} src={api.mediaUrl(ev.clip)} poster={ev.image ? api.mediaUrl(ev.image) : undefined}
          controls autoPlay muted loop playsInline onLoadedData={() => setState('ready')} onError={onError} />
        {state === 'loading' && <p className="note">Preparing clip… it includes a few seconds after the alert.</p>}
      </>
    )
  }
  return (
    <>
      {ev.image && <img src={api.mediaUrl(ev.image)} alt="alert snapshot" />}
      {ev.clip && <p className="note">The clip isn’t available (it may have been cleaned up, or ffmpeg is not installed). Showing the snapshot.</p>}
    </>
  )
}

/* ------------------------------------------------------------ evaluation */
const pct = (v: number | null | undefined) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`)

export function EvalPage() {
  const [res, setRes] = useState<EvalResult[] | null>(null)
  const [i, setI] = useState(0)
  useEffect(() => { api.evals().then(setRes).catch(() => setRes([])) }, [])
  const r = res?.[i]
  return (
    <div className="page">
      <div className="toolbar"><h2>Evaluation</h2><div className="spacer" />
        {res && res.length > 1 && <select value={i} onChange={(e) => setI(+e.target.value)}>{res.map((x, k) => <option key={k} value={k}>{x.name}</option>)}</select>}
      </div>
      <div className="callout">
        <b>Read results with their context.</b> Precision, recall, F1 and mAP only describe the dataset, classes and thresholds they were measured on.
        Do not quote one accuracy figure without saying which dataset, class, confidence threshold and method produced it.
      </div>

      {res === null && <div className="empty"><div className="spinner" />Loading…</div>}
      {res?.length === 0 && (
        <div className="empty"><h3>No evaluation runs yet</h3>
          <p>Run <code>cd backend && .venv/bin/python evaluate.py --weights models/yolo11n.pt --data your_data.yaml</code> and refresh.</p></div>
      )}
      {r && (
        <>
          <div className="cards">
            <div className="card"><span>Precision</span><b>{pct(r.overall.precision)}</b><small>at conf ≥ {r.conf_threshold}</small></div>
            <div className="card"><span>Recall</span><b>{pct(r.overall.recall)}</b><small>at conf ≥ {r.conf_threshold}</small></div>
            <div className="card"><span>F1</span><b>{pct(r.overall.f1)}</b><small>mean over classes</small></div>
            <div className="card"><span>mAP@50</span><b>{pct(r.overall.map50)}</b><small>IoU 0.50</small></div>
            <div className="card"><span>mAP@50-95</span><b>{pct(r.overall.map50_95)}</b><small>IoU 0.50–0.95</small></div>
            <div className="card"><span>Inference</span><b>{Math.round(r.speed_ms.inference ?? 0)}<em>ms</em></b><small>per image · {r.device}</small></div>
          </div>
          <section className="panel">
            <div className="panel-head"><h3>{r.name}</h3><span className="muted">{new Date(r.ts * 1000).toLocaleString()}</span></div>
            <div className="meta-row">
              <span>Weights <b>{r.weights}</b></span><span>Dataset <b>{r.dataset}</b></span>
              <span>Images <b>{r.images ?? '—'}</b></span><span>Image size <b>{r.imgsz}</b></span><span>NMS IoU <b>{r.iou_threshold}</b></span>
            </div>
            {r.note && <div className="callout warn">{r.note}</div>}
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Class</th><th>Instances</th><th>Precision</th><th>Recall</th><th>F1</th><th>mAP@50</th><th>mAP@50-95</th></tr></thead>
                <tbody>
                  {r.per_class.map((c) => (
                    <tr key={c.class}><td>{c.class}</td><td>{c.instances ?? '—'}</td><td>{pct(c.precision)}</td><td>{pct(c.recall)}</td>
                      <td>{pct(c.f1)}</td><td>{pct(c.map50)}</td><td>{pct(c.map50_95)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      <section className="panel">
        <div className="panel-head"><h3>Evaluate your own footage</h3></div>
        <ol className="steps">
          <li>Label representative frames (day / night, indoor / outdoor, crowded, different distances) in YOLO format and write a dataset <code>.yaml</code>.</li>
          <li>Run <code>.venv/bin/python evaluate.py --weights models/yolo11n.pt --data my_data.yaml --name "Site A · night"</code>.</li>
          <li>Results appear here. Compare per class and per camera condition rather than relying on one overall number.</li>
        </ol>
      </section>
    </div>
  )
}

/* ----------------------------------------------------------------- login */
export function LoginScreen({ onDone }: { onDone: (a: AuthState) => void }) {
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { onDone(await api.login(u, p)) } catch (x) { setErr((x as Error).message) } finally { setBusy(false) }
  }
  return (
    <div className="login">
      <form onSubmit={submit}>
        <img src="/logo.svg" width={56} height={56} alt="Vision Monitor" />
        <h1>Vision Monitor</h1>
        <p className="muted">Sign in to view cameras and alerts</p>
        <label className="field">Username<input value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" /></label>
        <label className="field">Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
        {err && <div className="form-err">{err}</div>}
        <button className="primary wide" disabled={busy || !u || !p}><Lock size={15} />{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </div>
  )
}
