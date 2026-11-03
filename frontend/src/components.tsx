import { useEffect, useRef, useState } from 'react'
import {
  Camera as CamIcon, Expand, FileVideo, Link2, Play, Plus, Radar, Square, Trash2, Upload, Video, X,
} from 'lucide-react'
import { api } from './api'
import type { Camera, DetEvent, Sample, Summary } from './types'

export const CAT_COLORS: Record<string, string> = {
  person: '#50dc64', car: '#ffaa3c', truck: '#3c8cff', bus: '#3cc8ff',
  motorcycle: '#ff5ac8', bicycle: '#e6e650', animal: '#5a78ff', object: '#c8c8c8', face: '#ffffff',
}
const CAT_LABEL: Record<string, string> = {
  person: 'People', car: 'Cars', truck: 'Trucks', bus: 'Buses', motorcycle: 'Motorcycles',
  bicycle: 'Bicycles', animal: 'Animals', object: 'Bags', face: 'Faces',
}
const CATS = ['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'animal', 'object']

const fmtUptime = (s: number) =>
  s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`

export function StatusBadge({ status }: { status: Camera['status'] }) {
  const label = { live: 'LIVE', starting: 'STARTING', error: 'ERROR', stopped: 'STOPPED' }[status]
  return <span className={`badge badge-${status}`}><i />{label}</span>
}

/* ------------------------------------------------------------------ tile */
export function CameraTile({
  cam, onExpand, onError,
}: { cam: Camera; onExpand: () => void; onError: (m: string) => void }) {
  const [nonce, setNonce] = useState(0)
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
          <img key={nonce} src={`${api.streamUrl(cam.id)}?n=${nonce}`} alt={cam.name} />
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
            {active
              ? <button className="icon" title="Stop" onClick={() => run(api.stop(cam.id))}><Square size={15} /></button>
              : <button className="icon" title="Start" onClick={() => run(api.start(cam.id))}><Play size={15} /></button>}
            <button className="icon danger" title="Remove camera"
              onClick={() => { if (confirm(`Remove "${cam.name}"?`)) run(api.remove(cam.id)) }}>
              <Trash2 size={15} />
            </button>
          </div>
        </div>
        <div className="metrics">
          <span><b>{cam.fps.toFixed(1)}</b> FPS</span>
          <span><b>{Math.round(cam.latency_ms)}</b> ms</span>
          <span>{cam.resolution || '—'}</span>
          <span>{fmtUptime(cam.uptime)}</span>
        </div>
        <div className="chips">
          {chips.length === 0 && <span className="muted">No detections yet</span>}
          {chips.map((c) => (
            <span key={c} className="chip" title={`${CAT_LABEL[c]}: ${cam.current[c]} in frame now · ${cam.unique[c]} unique tracked`}>
              <i style={{ background: CAT_COLORS[c] }} />{CAT_LABEL[c]} <b>{cam.current[c]}</b>
              <small>/{cam.unique[c]}</small>
            </span>
          ))}
          {cam.settings.faces && cam.current.face > 0 && (
            <span className="chip"><i style={{ background: CAT_COLORS.face }} />Faces <b>{cam.current.face}</b></span>
          )}
        </div>
      </div>
    </article>
  )
}

/* -------------------------------------------------------------- expanded */
export function ExpandedView({ cam, onClose, onError }: { cam: Camera; onClose: () => void; onError: (m: string) => void }) {
  const [conf, setConf] = useState(cam.settings.conf)
  const patch = (p: Record<string, unknown>) => api.patch(cam.id, p).catch((e) => onError(e.message))
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
          <div className="expanded-video">
            {cam.status === 'live'
              ? <img src={api.streamUrl(cam.id)} alt={cam.name} />
              : <div className="tile-placeholder big">{cam.error || `Camera ${cam.status}`}</div>}
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
                onChange={(e) => setConf(+e.target.value)} onMouseUp={() => patch({ conf })} onTouchEnd={() => patch({ conf })} onKeyUp={() => patch({ conf })} />
            </label>
            <label className="toggle"><input type="checkbox" checked={cam.settings.tracking}
              onChange={(e) => patch({ tracking: e.target.checked })} /> Object tracking (track IDs)</label>
            <label className="toggle"><input type="checkbox" checked={cam.settings.faces}
              onChange={(e) => patch({ faces: e.target.checked })} /> Face detection (no identification)</label>
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
const EV_ICON: Record<string, string> = { new_track: '◆', camera_online: '●', camera_offline: '○', camera_error: '▲' }

export function EventFeed({ events }: { events: DetEvent[] }) {
  return (
    <section className="panel">
      <div className="panel-head"><h3>Event log</h3><a className="link" href="/api/report.csv">Export CSV</a></div>
      <ul className="events">
        {events.length === 0 && <li className="muted">No events yet</li>}
        {events.slice(0, 40).map((e) => (
          <li key={e.id} className={`ev ev-${e.type}`}>
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
        <li><b>Not built yet:</b> helmet / PPE, pose, zones, clothing — need custom-trained models.</li>
        <li>Proof of concept: no accuracy claim without evaluation on representative footage.</li>
        <li>Unique counts are per tracking session and can over- or under-count.</li>
      </ul>
    </section>
  )
}
