import { useEffect, useRef, useState } from 'react'
import {
  Camera as CamIcon, Expand, FileVideo, Flame, Link2, Pencil, Play, Plus, Radar, Square, Trash2, Upload, Video, X,
} from 'lucide-react'
import { api } from './api'
import type { AtmospherePoint, Camera, DetectorInfo, DetEvent, Sample, Summary } from './types'

export const CAT_COLORS: Record<string, string> = {
  person: '#50dc64', car: '#ffaa3c', truck: '#3c8cff', bus: '#3cc8ff',
  motorcycle: '#ff5ac8', bicycle: '#e6e650', animal: '#5a78ff', object: '#c8c8c8', face: '#ffffff',
}
const CAT_LABEL: Record<string, string> = {
  person: 'People', car: 'Cars', truck: 'Trucks', bus: 'Buses', motorcycle: 'Motorcycles',
  bicycle: 'Bicycles', animal: 'Animals', object: 'Bags', face: 'Faces',
}
const POSTURE_KEYS = ['standing', 'sitting', 'bending', 'lying']
const CATS = ['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'animal', 'object']

const fmtUptime = (s: number) =>
  s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`

export function StatusBadge({ status }: { status: Camera['status'] }) {
  const label = { live: 'LIVE', starting: 'STARTING', error: 'ERROR', stopped: 'STOPPED' }[status]
  return <span className={`badge badge-${status}`}><i />{label}</span>
}

/** Live view built from short snapshot requests instead of a long-lived MJPEG connection.
 *  Browsers allow only ~6 open connections per host, so one persistent stream per camera
 *  starves every other request (the expanded view, settings, API calls) once 6+ cameras run. */
export function LiveFrame({ id, alt, fast = false }: { id: string; alt: string; fast?: boolean }) {
  const [src, setSrc] = useState('')
  useEffect(() => {
    let stop = false
    let timer: number | undefined
    const next = () => {
      const im = new Image()
      im.onload = () => { if (stop) return; setSrc(im.src); timer = window.setTimeout(next, fast ? 80 : 250) }
      im.onerror = () => { if (!stop) timer = window.setTimeout(next, 1000) }
      im.src = `${api.snapshotUrl(id)}?t=${Date.now()}`
    }
    next()
    return () => { stop = true; clearTimeout(timer) }
  }, [id, fast])
  return src ? <img src={src} alt={alt} /> : <div className="tile-placeholder"><div className="spinner" /></div>
}

/** "Detect anything": type an object name and an open-vocabulary model looks for it (no training). */
function CustomObjects({ cam, st, readOnly, patch }: { cam: Camera; st: Camera['settings']; readOnly: boolean; patch: (p: Record<string, unknown>) => void }) {
  const [text, setText] = useState('')
  const prompts = st.custom ?? []
  const [conf, setConf] = useState(st.custom_conf ?? 0.2)
  const available = cam.features.world_available !== false
  const add = () => {
    const v = text.trim().toLowerCase()
    if (!v || prompts.includes(v) || prompts.length >= 8) return
    patch({ custom: [...prompts, v] }); setText('')
  }
  return (
    <div className="custom-box">
      <h4>Detect anything <small>· type an object</small></h4>
      {!available && <p className="note err">Model not installed. Run backend/download_models.sh</p>}
      {!readOnly && (
        <form className="custom-add" onSubmit={(e) => { e.preventDefault(); add() }}>
          <input value={text} maxLength={40} disabled={!available || prompts.length >= 8}
            placeholder="e.g. forklift, hard hat, umbrella" onChange={(e) => setText(e.target.value)} />
          <button className="ghost" type="submit" disabled={!text.trim() || !available}><Plus size={14} />Add</button>
        </form>
      )}
      {prompts.length > 0 && (
        <div className="custom-chips">
          {prompts.map((p) => (
            <span key={p} className="chip custom">{p} <b>{cam.custom?.counts?.[p] ?? 0}</b>
              {!readOnly && <button title={`Remove ${p}`} onClick={() => patch({ custom: prompts.filter((x) => x !== p) })}><X size={11} /></button>}
            </span>
          ))}
        </div>
      )}
      {cam.custom?.loading && <p className="note"><span className="spinner sm" /> Loading open-vocabulary model…</p>}
      {cam.custom?.error && <p className="note err">{cam.custom.error}</p>}
      {prompts.length > 0 && (
        <label className="field">Custom confidence <b>{conf.toFixed(2)}</b>
          <input type="range" min={0.05} max={0.8} step={0.05} value={conf} disabled={readOnly}
            onChange={(e) => setConf(+e.target.value)} onMouseUp={() => patch({ custom_conf: conf })}
            onTouchEnd={() => patch({ custom_conf: conf })} onKeyUp={() => patch({ custom_conf: conf })} />
        </label>
      )}
      <p className="note">Zero-shot: no training, so it is less accurate than the built-in classes. Short, concrete nouns work best. Violet boxes in the video.</p>
    </div>
  )
}

/** Visibility index, level and a short trend for one camera. */
function AtmospherePanel({ cam }: { cam: Camera }) {
  const [hist, setHist] = useState<AtmospherePoint[]>([])
  useEffect(() => {
    let stop = false
    const load = () => api.atmosphere(cam.id).then((r) => { if (!stop) setHist(r.history) }).catch(() => {})
    load()
    const t = setInterval(load, 5000)
    return () => { stop = true; clearInterval(t) }
  }, [cam.id])
  const a = cam.atmosphere
  if (!a) return <p className="note">Measuring visibility…</p>
  const label = a.level === 'night' ? 'Night — not assessed'
    : a.level === 'clear' ? 'Clear'
    : `${a.level === 'dense' ? 'Dense ' : a.level === 'foggy' ? '' : 'Light '}${a.kind === 'smog' ? 'smog / possible pollution' : 'fog'}`
  const pts = hist.filter((p) => p.visibility !== null)
  const W = 240, H = 44
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${(pts.length <= 1 ? 0 : (i / (pts.length - 1)) * W).toFixed(1)},${(H - ((p.visibility as number) / 100) * H).toFixed(1)}`).join(' ')
  return (
    <div className={`air-panel ${a.level}`}>
      <div className="air-head"><b>{a.visibility === null ? '—' : Math.round(a.visibility)}</b><span>/100 visibility</span><em>{label}</em></div>
      {pts.length > 1 && (
        <svg viewBox={`0 0 ${W} ${H}`} className="air-spark" role="img" aria-label="Visibility trend">
          <path d={path} fill="none" stroke="currentColor" strokeWidth="1.6" />
        </svg>
      )}
      <p className="note">Relative index from image contrast, not a distance in metres. It cannot measure PM2.5 / AQI; a warm tint is only a hint of smog or dust.</p>
    </div>
  )
}

/** Themed replacement for window.confirm(), which cannot be styled and blocks the page. */
export function ConfirmDialog({ title, message, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel }: {
  title: string; message: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void; onCancel: () => void
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onCancel() }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onCancel])
  return (
    <div className="overlay confirm-overlay" onClick={(e) => { e.stopPropagation(); onCancel() }} role="presentation">
      <div className="confirm" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" onClick={(e) => e.stopPropagation()}>
        <h3 id="confirm-title">{title}</h3>
        <p>{message}</p>
        <div className="confirm-actions">
          <button className="ghost" onClick={onCancel} autoFocus>Cancel</button>
          <button className={danger ? 'danger-btn' : 'primary'} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ tile */
export function CameraTile({
  cam, onExpand, onError, readOnly = false,
}: { cam: Camera; onExpand: () => void; onError: (m: string) => void; readOnly?: boolean }) {
  const [nonce, setNonce] = useState(0)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const prev = useRef(cam.status)
  useEffect(() => {
    if (prev.current !== 'live' && cam.status === 'live') setNonce((n) => n + 1) // re-open the MJPEG stream
    prev.current = cam.status
  }, [cam.status])

  const run = (p: Promise<unknown>) => p.catch((e) => onError(e.message))
  const active = cam.status === 'live' || cam.status === 'starting'
  const chips = CATS.filter((c) => cam.current[c] > 0 || cam.unique[c] > 0)

  return (
    <article className={`tile tile-${cam.status}`}>
      <div className="tile-video" onDoubleClick={onExpand}>
        {cam.status === 'live' ? (
          <LiveFrame key={nonce} id={cam.id} alt={cam.name} />
        ) : (
          <div className="tile-placeholder">
            {cam.status === 'starting' && <><div className="spinner" /><span>Loading model & opening source…</span></>}
            {cam.status === 'stopped' && <><Square size={22} /><span>Camera stopped</span></>}
            {cam.status === 'error' && <><X size={22} /><span className="err">{cam.error}</span></>}
          </div>
        )}
        <div className="tile-top">
          <StatusBadge status={cam.status} />
          <span className="kind">
            {cam.kind === 'webcam' ? <CamIcon size={12} /> : cam.kind === 'file' ? <FileVideo size={12} /> : <Link2 size={12} />}
            {cam.kind === 'rtsp' ? 'stream' : cam.kind}
          </span>
        </div>
      </div>
      <div className="tile-body">
        <div className="tile-head">
          <h3 title={cam.name}>{cam.name}</h3>
          <div className="actions">
            <button className="icon" title="Expand" onClick={onExpand}><Expand size={15} /></button>
            {!readOnly && (active
              ? <button className="icon" title="Stop" onClick={() => run(api.stop(cam.id))}><Square size={15} /></button>
              : <button className="icon" title="Start" onClick={() => run(api.start(cam.id))}><Play size={15} /></button>)}
            {!readOnly && (
              <button className="icon danger" title="Remove camera"
                onClick={() => setConfirmRemove(true)}>
                <Trash2 size={15} />
              </button>
            )}
          </div>
        </div>
        <div className="metrics">
          <span><b>{cam.fps.toFixed(1)}</b> FPS</span>
          <span><b>{Math.round(cam.latency_ms)}</b> ms</span>
          <span>{cam.resolution || '—'}</span>
          <span>{fmtUptime(cam.uptime)}</span>
        </div>
        <div className="chips">
          {chips.length === 0 && !(cam.settings.zones?.length || cam.settings.lines?.length) && <span className="muted">No detections yet</span>}
          {chips.map((c) => (
            <span key={c} className="chip" title={`${CAT_LABEL[c]}: ${cam.current[c]} in frame now · ${cam.unique[c]} unique tracked`}>
              <i style={{ background: CAT_COLORS[c] }} />{CAT_LABEL[c]} <b>{cam.current[c]}</b>
              <small>/{cam.unique[c]}</small>
            </span>
          ))}
          {cam.settings.faces && cam.current.face > 0 && (
            <span className="chip"><i style={{ background: CAT_COLORS.face }} />Faces <b>{cam.current.face}</b></span>
          )}
          {(cam.settings.zones ?? []).map((z) => (
            <span key={z.id} className="chip zone" title={`Zone “${z.name}”: ${cam.rules?.zones[z.id]?.occupancy ?? 0} inside now · ${cam.rules?.zones[z.id]?.entries ?? 0} entries`}>
              <i style={{ background: z.color, borderRadius: 2 }} />{z.name} <b>{cam.rules?.zones[z.id]?.occupancy ?? 0}</b>
              <small>/{cam.rules?.zones[z.id]?.entries ?? 0} in</small>
            </span>
          ))}
          {(cam.settings.lines ?? []).map((l) => (
            <span key={l.id} className="chip line" title={`Line “${l.name}”: crossings in / out`}>
              <i style={{ background: '#3cc8ff', borderRadius: 2, height: 3 }} />{l.name} <b>↓{cam.rules?.lines[l.id]?.in ?? 0}</b> <b>↑{cam.rules?.lines[l.id]?.out ?? 0}</b>
            </span>
          ))}
          {cam.settings.privacy && <span className="chip privacy">Privacy</span>}
          {cam.health && !['ok', 'off'].includes(cam.health.state) && (
            <span className="chip health-bad">{{ frozen: 'Frozen', blocked: 'Blocked', blurred: 'Blurred', moved: 'Moved', stalled: 'No frames' }[cam.health.state as string]}</span>
          )}
          {Object.entries(cam.custom?.counts ?? {}).filter(([, n]) => n > 0).map(([name, n]) => (
            <span key={name} className="chip custom">{name} <b>{n}</b></span>
          ))}
          {cam.settings.atmosphere && cam.atmosphere && cam.atmosphere.level !== 'clear' && (
            <span className={`chip air ${cam.atmosphere.level}`}>
              {cam.atmosphere.level === 'night' ? 'Night' : `${cam.atmosphere.kind === 'smog' ? 'Smog' : cam.atmosphere.level === 'hazy' ? 'Haze' : 'Fog'} · ${Math.round(cam.atmosphere.visibility ?? 0)}`}
            </span>
          )}
          {cam.settings.pose && Object.entries(cam.postures ?? {}).filter(([, n]) => n > 0).map(([p, n]) => (
            <span key={p} className="chip pose">{p} <b>{n}</b></span>
          ))}
        </div>
      </div>
    {confirmRemove && (
        <ConfirmDialog title={`Remove ${cam.name}?`} danger confirmLabel="Remove camera"
          message="The camera and its live view are removed. Stored events and alert clips are kept."
          onCancel={() => setConfirmRemove(false)} onConfirm={() => { setConfirmRemove(false); run(api.remove(cam.id)) }} />
      )}
    </article>
  )
}

/* -------------------------------------------------------------- expanded */
export function ExpandedView({
  cam, onClose, onError, onEditZones, readOnly = false,
}: { cam: Camera; onClose: () => void; onError: (m: string) => void; onEditZones: () => void; readOnly?: boolean }) {
  const [conf, setConf] = useState(cam.settings.conf)
  // optimistic toggles: reflect the click immediately, drop the override once the server state catches up
  const [opt, setOpt] = useState<Partial<Camera['settings']>>({})
  const st = { ...cam.settings, ...opt }
  useEffect(() => {
    const keys = Object.keys(opt) as (keyof Camera['settings'])[]
    if (keys.length && keys.every((k) => cam.settings[k] === opt[k])) setOpt({})
  }, [cam.settings, opt])
  useEffect(() => { if (Object.keys(opt).length) { const t = setTimeout(() => setOpt({}), 4000); return () => clearTimeout(t) } }, [opt])
  const [heat, setHeat] = useState(false)
  const [det, setDet] = useState<DetectorInfo | null>(null)
  useEffect(() => { api.detector().then(setDet).catch(() => {}) }, [])
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (!heat) return
    const t = setInterval(() => setTick((n) => n + 1), 1500)
    return () => clearInterval(t)
  }, [heat])
  const patch = (p: Record<string, unknown>) => {
    setOpt((o) => ({ ...o, ...p } as Partial<Camera['settings']>))
    return api.patch(cam.id, p).catch((e) => { setOpt({}); onError(e.message) })
  }
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="expanded" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>{cam.name}</h2><StatusBadge status={cam.status} />
          <button className="icon" onClick={onClose}><X size={18} /></button>
        </header>
        <div className="expanded-main">
          <div className="expanded-left">
          <div className="expanded-video">
            {cam.status === 'live'
              ? (heat
                ? <img key="heat" src={`${api.heatmapUrl(cam.id)}?t=${tick}`} alt={`${cam.name} heatmap`} />
                : <LiveFrame key="live" id={cam.id} alt={cam.name} fast />)
              : <div className="tile-placeholder big">{cam.error || `Camera ${cam.status}`}</div>}
          </div>
          <div className="view-bar">
            <div className="seg">
              <button className={!heat ? 'on' : ''} onClick={() => setHeat(false)}>Live</button>
              <button className={heat ? 'on' : ''} onClick={() => setHeat(true)}><Flame size={13} />Heatmap</button>
            </div>
            {heat && !readOnly && <button className="link" onClick={() => api.resetHeat(cam.id).catch((e) => onError(e.message))}>Reset heatmap</button>}
            {heat && <span className="muted">where people and vehicles spent time since the camera started</span>}
          </div>
          </div>
          <aside>
            <h4>Live counts</h4>
            <table>
              <thead><tr><th>Class</th><th title="Objects visible in the current frame">Now</th><th title="Distinct tracking IDs since the stream started">Unique</th></tr></thead>
              <tbody>
                {CATS.map((c) => (
                  <tr key={c}><td><i className="dot" style={{ background: CAT_COLORS[c] }} />{CAT_LABEL[c]}</td>
                    <td>{cam.current[c]}</td><td>{cam.unique[c]}</td></tr>
                ))}
                <tr><td><i className="dot" style={{ background: CAT_COLORS.face }} />Faces</td><td>{cam.current.face}</td><td>—</td></tr>
              </tbody>
            </table>
            <p className="note">“Unique” counts distinct ByteTrack IDs. It can overcount when someone is lost and re-acquired after occlusion.</p>

            <h4>Settings</h4>
            <label className="field">Confidence threshold <b>{conf.toFixed(2)}</b>
              <input type="range" min={0.1} max={0.9} step={0.05} value={conf}
                disabled={readOnly} onChange={(e) => setConf(+e.target.value)} onMouseUp={() => patch({ conf })} onTouchEnd={() => patch({ conf })} onKeyUp={() => patch({ conf })} />
            </label>
            <label className="field">Detection model
              <select value={st.model ?? ''} disabled={readOnly} onChange={(e) => patch({ model: e.target.value })}>
                <option value="">Default ({det?.options.find((o) => o.file === det.current)?.label ?? det?.current ?? '…'})</option>
                {det?.options.filter((o) => o.installed).map((o) => <option key={o.file} value={o.file}>{o.label} · {o.file}</option>)}
              </select>
            </label>
            <label className="toggle"><input type="checkbox" checked={st.tracking} disabled={readOnly}
              onChange={(e) => patch({ tracking: e.target.checked })} /> Object tracking (track IDs)</label>
            <label className="toggle"><input type="checkbox" checked={st.faces} disabled={readOnly}
              onChange={(e) => patch({ faces: e.target.checked })} /> Face detection (no identification)</label>
            <label className="toggle" title={cam.features.pose_available ? '' : 'Pose model not installed'}>
              <input type="checkbox" checked={st.pose} disabled={readOnly || !cam.features.pose_available}
                onChange={(e) => patch({ pose: e.target.checked })} /> Pose &amp; posture (skeleton, fall check)</label>
            <label className="toggle" title={cam.features.ppe_available ? '' : 'Add a custom-trained model at backend/models/ppe.pt'}>
              <input type="checkbox" checked={st.ppe} disabled={readOnly || !cam.features.ppe_available}
                onChange={(e) => patch({ ppe: e.target.checked })} /> Helmet / PPE{!cam.features.ppe_available && <em className="muted"> · needs model</em>}</label>
            <label className="toggle" title="Estimates fog, haze and smog from image contrast. Best for outdoor cameras with a view into the distance.">
              <input type="checkbox" checked={st.atmosphere ?? false} disabled={readOnly}
                onChange={(e) => patch({ atmosphere: e.target.checked })} /> Weather &amp; visibility (fog / haze / smog)</label>
            {cam.features.pose_error && <p className="note err">{cam.features.pose_error}</p>}
            {cam.features.ppe_error && st.ppe && <p className="note err">{cam.features.ppe_error}</p>}
            {st.pose && (
              <p className="note">Posture now: {POSTURE_KEYS.map((k) => `${k} ${cam.postures?.[k] ?? 0}`).join(' · ')}. A “lying” person for 1.5 s raises a <b>possible fall</b> alert for human review.</p>
            )}
            {st.ppe && cam.features.ppe_available && (
              <p className="note">Helmet: {cam.ppe?.helmet_yes ?? 0} yes · {cam.ppe?.helmet_no ?? 0} no · {cam.ppe?.helmet_unknown ?? 0} unknown (not enough evidence)</p>
            )}
            {st.atmosphere && <AtmospherePanel cam={cam} />}
            <label className="toggle" title="Stores a small thumbnail and CLIP embedding every few seconds so you can search this camera in plain words on the Search page.">
              <input type="checkbox" checked={st.index ?? false} disabled={readOnly}
                onChange={(e) => patch({ index: e.target.checked })} /> Searchable footage (Search page)</label>
            {cam.index?.error && st.index && <p className="note err">{cam.index.error}</p>}
            <label className="toggle" title="Pixelates faces (and the head of people whose face is not detected) before anything is streamed, saved or recorded.">
              <input type="checkbox" checked={st.privacy ?? false} disabled={readOnly}
                onChange={(e) => patch({ privacy: e.target.checked })} /> Privacy mode (blur faces)</label>
            <label className="toggle" title="Alerts when the picture freezes, the lens is blocked, the image blurs or the camera is moved. Off by default for looping video files.">
              <input type="checkbox" checked={st.health ?? cam.health?.enabled ?? false} disabled={readOnly}
                onChange={(e) => patch({ health: e.target.checked })} /> Camera health &amp; tamper alerts</label>
            {cam.health?.enabled && (
              <p className={`note ${cam.health.state === 'ok' ? '' : 'err'}`}>
                Health: <b>{cam.health.state === 'ok' ? 'OK' : cam.health.state}</b> · reconnects {cam.health.reconnects}
                {cam.health.metrics?.sharpness !== undefined && <> · sharpness {cam.health.metrics.sharpness}</>}
              </p>
            )}
            <CustomObjects cam={cam} st={st} readOnly={readOnly} patch={patch} />
            <h4>Zones &amp; lines</h4>
            <button className="ghost" onClick={onEditZones}><Pencil size={14} />{readOnly ? 'View' : 'Edit'} zones &amp; lines ({(cam.settings.zones?.length ?? 0) + (cam.settings.lines?.length ?? 0)})</button>
            {(cam.settings.zones ?? []).map((z) => (
              <div key={z.id} className="stat-line"><span><i className="dot" style={{ background: z.color }} />{z.name}</span><b>{cam.rules?.zones[z.id]?.occupancy ?? 0} now · {cam.rules?.zones[z.id]?.entries ?? 0} entries</b></div>
            ))}
            {(cam.settings.lines ?? []).map((l) => (
              <div key={l.id} className="stat-line"><span><i className="dot" style={{ background: '#3cc8ff' }} />{l.name}</span><b>↓ in {cam.rules?.lines[l.id]?.in ?? 0} · ↑ out {cam.rules?.lines[l.id]?.out ?? 0}</b></div>
            ))}
            <p className="note">Boxes below 0.45 confidence are drawn thin with a “?” rather than shown as certain.</p>
            <div className="stat-line">Inference device <b>{cam.device}</b></div>
            <div className="stat-line">Frame detections (cumulative) <b>{cam.detections_total.toLocaleString()}</b></div>
          </aside>
        </div>
      </div>
    </div>
  )
}

/* ----------------------------------------------------------- add camera */
type Tab = 'webcam' | 'sample' | 'upload' | 'stream'

export function AddCameraModal({ onClose, onAdded, onError }: { onClose: () => void; onAdded: () => void; onError: (m: string) => void }) {
  const [tab, setTab] = useState<Tab>('sample')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [webcams, setWebcams] = useState<{ index: number; in_use: boolean }[] | null>(null)
  const [samples, setSamples] = useState<Sample[]>([])
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => { api.samples().then(setSamples).catch(() => {}) }, [])
  const scan = () => { setWebcams(null); api.discover().then(setWebcams).catch((e) => { onError(e.message); setWebcams([]) }) }
  useEffect(() => { if (tab === 'webcam' && webcams === null) scan() }, [tab]) // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (p: Promise<unknown>) => {
    setBusy(true)
    try { await p; onAdded(); onClose() } catch (e) { onError((e as Error).message) } finally { setBusy(false) }
  }

  const tabs: [Tab, string, React.ReactNode][] = [
    ['sample', 'Sample videos', <Video size={14} />], ['webcam', 'Local webcam', <CamIcon size={14} />],
    ['upload', 'Upload video', <Upload size={14} />], ['stream', 'RTSP / URL', <Link2 size={14} />],
  ]

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header><h2>Add camera</h2><button className="icon" onClick={onClose}><X size={18} /></button></header>
        <nav className="tabs">
          {tabs.map(([t, l, i]) => <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{i}{l}</button>)}
        </nav>
        <label className="field">Display name (optional)
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Main gate" maxLength={40} />
        </label>

        {tab === 'sample' && (
          <div className="list">
            {samples.length === 0 && <p className="muted">No samples found. Run <code>backend/download_samples.sh</code>.</p>}
            {samples.map((s) => (
              <button key={s.file} className="row" disabled={busy}
                onClick={() => submit(api.addCamera({ name: name || s.name, kind: 'file', source: s.file }))}>
                <FileVideo size={16} />{s.name}<Plus size={16} />
              </button>
            ))}
          </div>
        )}
        {tab === 'webcam' && (
          <div className="list">
            {webcams === null && <p className="muted">Scanning for cameras…</p>}
            {webcams?.length === 0 && <p className="muted">No webcam found. On macOS, allow camera access for your terminal in System Settings → Privacy &amp; Security → Camera.</p>}
            {webcams?.map((w) => (
              <button key={w.index} className="row" disabled={busy || w.in_use}
                onClick={() => submit(api.addCamera({ name: name || `Webcam ${w.index}`, kind: 'webcam', source: String(w.index) }))}>
                <CamIcon size={16} />Webcam {w.index}{w.in_use ? <em>already added</em> : <Plus size={16} />}
              </button>
            ))}
            <button className="link" onClick={scan}>Rescan</button>
          </div>
        )}
        {tab === 'upload' && (
          <div className="list">
            <label className="drop">
              <Upload size={20} />{file ? file.name : 'Choose a video (mp4, mov, avi, mkv, webm · max 300 MB)'}
              <input type="file" accept="video/*" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </label>
            <button className="primary" disabled={!file || busy}
              onClick={() => file && submit(api.upload(file, name))}>{busy ? 'Uploading…' : 'Upload & analyse'}</button>
          </div>
        )}
        {tab === 'stream' && (
          <div className="list">
            <label className="field">Stream URL
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="rtsp://user:pass@192.168.1.10:554/stream1" />
            </label>
            <button className="primary" disabled={!url.trim() || busy}
              onClick={() => submit(api.addCamera({ name: name || 'IP camera', kind: 'rtsp', source: url.trim() }))}>Connect</button>
          </div>
        )}
      </div>
    </div>
  )
}

/* --------------------------------------------------------------- sidebar */
const EV_ICON: Record<string, string> = {
  new_track: '◆', camera_online: '●', camera_offline: '○', camera_error: '▲', line_cross: '⇅', zone_enter: '▣',
  zone_exit: '▢', dwell: '◷', capacity: '⚑', fall: '⚠', ppe_violation: '⛑', visibility: '≋', custom_detect: '◇', camera_tamper: '⚠', camera_tamper_clear: '✓', camera_reconnecting: '↻', visibility_clear: '☀',
}

export function EventFeed({ events }: { events: DetEvent[] }) {
  return (
    <section className="panel">
      <div className="panel-head"><h3>Event log</h3><a className="link" href="/api/report.csv">Export CSV</a></div>
      <ul className="events">
        {events.length === 0 && <li className="muted">No events yet</li>}
        {events.slice(0, 40).map((e) => (
          <li key={e.id} className={`ev ev-${e.type} ${e.severity === 'alert' ? 'ev-alert' : ''}`}>
            <span className="ev-ic">{EV_ICON[e.type] ?? '•'}</span>
            <span className="ev-msg">{e.message}<small>{e.camera_name}{e.confidence ? ` · ${(e.confidence * 100).toFixed(0)}%` : ''}</small></span>
            <time>{new Date(e.ts * 1000).toLocaleTimeString()}</time>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function TotalsPanel({ s }: { s: Summary }) {
  const max = Math.max(1, ...CATS.map((c) => s.unique[c] ?? 0))
  return (
    <section className="panel">
      <div className="panel-head"><h3>All cameras</h3><span className="muted">now / unique</span></div>
      <div className="bars">
        {CATS.map((c) => (
          <div key={c} className="bar">
            <span>{CAT_LABEL[c]}</span>
            <div className="track"><div style={{ width: `${((s.unique[c] ?? 0) / max) * 100}%`, background: CAT_COLORS[c] }} /></div>
            <b>{s.current[c] ?? 0}<small>/{s.unique[c] ?? 0}</small></b>
          </div>
        ))}
      </div>
    </section>
  )
}

export function AboutPanel() {
  return (
    <section className="panel about">
      <div className="panel-head"><h3><Radar size={14} /> Model &amp; limitations</h3></div>
      <ul>
        <li><b>Pre-trained (COCO):</b> person, vehicles, animals, bags — YOLO11n + ByteTrack.</li>
        <li><b>Face:</b> YuNet detector — locates faces only; no identity recognition.</li>
        <li><b>Pose &amp; posture:</b> YOLO11n-pose with rule-based posture; fall alerts need human review.</li>
        <li><b>Zones, lines, dwell:</b> rule engine on tracked foot points — not a model.</li>
        <li><b>Helmet / PPE:</b> pipeline ready; needs a custom-trained <code>ppe.pt</code>. Without evidence a person is “unknown”, never “no helmet”.</li>
        <li><b>Not built:</b> clothing classification and identity recognition (by design).</li>
        <li>Proof of concept: no accuracy claim without evaluation on representative footage.</li>
        <li>Unique counts are per tracking session and can over- or under-count.</li>
      </ul>
    </section>
  )
}
