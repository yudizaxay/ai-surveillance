import { useCallback, useEffect, useState } from 'react'
import { Database, Search, Trash2, X } from 'lucide-react'
import { api } from './api'
import { ConfirmDialog } from './components'
import type { Camera, SearchHit, SearchStatus } from './types'

const EXAMPLES = ['person in a red jacket', 'white car', 'someone carrying a bag', 'bicycle', 'empty aisle', 'foggy trees', 'person wearing a helmet']
const RANGES: [string, number][] = [['Any time', 0], ['Last hour', 60], ['Last 24 h', 1440]]

// CLIP cosine similarities for a real match sit around 0.28-0.40; below ~0.25 it is mostly look-alikes.
const strength = (s: number) => (s >= 0.3 ? 'strong' : s >= 0.25 ? 'possible' : 'weak')

export function SearchPage({ cameras, readOnly }: { cameras: Camera[]; readOnly: boolean }) {
  const [q, setQ] = useState('')
  const [cam, setCam] = useState('')
  const [range, setRange] = useState(0)
  const [hits, setHits] = useState<SearchHit[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [status, setStatus] = useState<SearchStatus | null>(null)
  const [open, setOpen] = useState<SearchHit | null>(null)
  const [askClear, setAskClear] = useState(false)

  const loadStatus = useCallback(() => api.searchStatus().then(setStatus).catch(() => {}), [])
  useEffect(() => { loadStatus(); const t = setInterval(loadStatus, 4000); return () => clearInterval(t) }, [loadStatus])
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(null)
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [])

  const run = async (text = q) => {
    const query = text.trim()
    if (!query) return
    setQ(query); setBusy(true); setErr('')
    try { setHits(await api.search(query, cam, range)) }
    catch (e) { setErr((e as Error).message); setHits(null) }
    finally { setBusy(false) }
  }

  const allOn = cameras.length > 0 && cameras.every((c) => c.settings.index)
  const toggleAll = () => Promise.all(cameras.map((c) => api.patch(c.id, { index: !allOn }))).then(loadStatus).catch((e) => setErr(e.message))
  const clear = () => { setAskClear(false); api.clearIndex().then(() => { setHits(null); loadStatus() }) }

  return (
    <div className="search-page">
      <section className="panel search-box">
        <form onSubmit={(e) => { e.preventDefault(); run() }}>
          <Search size={18} />
          <input value={q} onChange={(e) => setQ(e.target.value)} maxLength={200} autoFocus
            placeholder="Describe what you are looking for, e.g. “person in a red jacket near the shelves”" />
          <select value={cam} onChange={(e) => setCam(e.target.value)} aria-label="Camera">
            <option value="">All cameras</option>
            {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={range} onChange={(e) => setRange(+e.target.value)} aria-label="Time range">
            {RANGES.map(([l, v]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="primary" type="submit" disabled={busy || !q.trim()}>{busy ? 'Searching…' : 'Search'}</button>
        </form>
        <div className="examples">
          {EXAMPLES.map((e) => <button key={e} type="button" className="chip" onClick={() => run(e)}>{e}</button>)}
        </div>
      </section>

      <section className="index-bar">
        <Database size={15} />
        <span><b>{status?.frames ?? 0}</b> frames indexed · {status?.indexing.length ?? 0}/{cameras.length} cameras indexing (one every {status?.every_s ?? 10}s, newest {status?.max_frames ?? 4000} kept)</span>
        {!readOnly && (
          <span className="index-actions">
            <button className="ghost" onClick={toggleAll}>{allOn ? 'Stop indexing all' : 'Index all cameras'}</button>
            <button className="ghost danger" onClick={() => setAskClear(true)} disabled={!status?.frames}><Trash2 size={13} />Clear</button>
          </span>
        )}
      </section>

      {status && !status.available && <p className="note err">The search model is not installed. Run backend/download_models.sh.</p>}
      {err && <p className="note err">{err}</p>}
      {hits === null && !err && (
        <div className="empty-search">
          <p>Search what your cameras have seen, in plain words.</p>
          <small>Switch on <b>Searchable footage</b> for a camera (or “Index all cameras” above), let it run for a bit, then search. It understands colours, objects and scenes; it does not read text or count things.</small>
        </div>
      )}
      {hits && hits.length === 0 && <p className="muted">Nothing indexed yet for this filter. Turn on indexing and give it a minute.</p>}
      {hits && hits.length > 0 && (
        <div className="hits">
          {hits.map((h) => (
            <figure key={h.frame_id} className={`hit ${strength(h.score)}`} onClick={() => setOpen(h)}>
              <div className="hit-img">
                <img src={api.indexUrl(h.thumb)} alt={`${h.camera_name} at ${new Date(h.ts * 1000).toLocaleTimeString()}`} loading="lazy" />
                {h.box && <i style={{ left: `${h.box[0] * 100}%`, top: `${h.box[1] * 100}%`, width: `${(h.box[2] - h.box[0]) * 100}%`, height: `${(h.box[3] - h.box[1]) * 100}%` }} />}
              </div>
              <figcaption>
                <b>{h.camera_name}</b>{h.label && <span className="chip custom">{h.label}</span>}
                <small>{new Date(h.ts * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit' })}</small>
                <em title={`similarity ${h.score.toFixed(3)}`}>{strength(h.score)} match</em>
              </figcaption>
            </figure>
          ))}
        </div>
      )}

      {askClear && (
        <ConfirmDialog title="Clear the search index?" danger confirmLabel="Clear index"
          message="All indexed thumbnails and embeddings are deleted. Alerts, clips and events are not affected."
          onCancel={() => setAskClear(false)} onConfirm={clear} />
      )}

      {open && (
        <div className="overlay" onClick={() => setOpen(null)}>
          <div className="expanded" onClick={(e) => e.stopPropagation()}>
            <header><h2>{open.camera_name} · {new Date(open.ts * 1000).toLocaleString()}</h2>
              <button className="icon" onClick={() => setOpen(null)}><X size={18} /></button></header>
            <div className="hit-img big">
              <img src={api.indexUrl(open.thumb)} alt="indexed frame" />
              {open.box && <i style={{ left: `${open.box[0] * 100}%`, top: `${open.box[1] * 100}%`, width: `${(open.box[2] - open.box[0]) * 100}%`, height: `${(open.box[3] - open.box[1]) * 100}%` }} />}
            </div>
            <p className="note">Similarity {open.score.toFixed(3)} ({strength(open.score)}). Similarity is not a probability: look at the picture before trusting it.</p>
          </div>
        </div>
      )}
    </div>
  )
}
