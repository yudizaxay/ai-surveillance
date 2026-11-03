import { useEffect, useMemo, useRef, useState } from 'react'
import { Minus, MousePointer2, Pentagon, Trash2, X } from 'lucide-react'
import { api } from './api'
import { ConfirmDialog } from './components'
import type { Camera, Line, Pt, Zone } from './types'

const COLORS = ['#3dd6c6', '#ffb020', '#ff5ac8', '#5a78ff', '#e6e650', '#ff5d5d']
const CLASSES = ['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'animal', 'object']
const uid = () => Math.random().toString(36).slice(2, 8)
const clamp = (v: number) => Math.min(1, Math.max(0, v))

type Tool = 'select' | 'polygon' | 'line'
type Sel = { kind: 'zone' | 'line'; id: string } | null

export function ZoneEditor({ cam, readOnly, onClose, onError }: { cam: Camera; readOnly: boolean; onClose: () => void; onError: (m: string) => void }) {
  const [zones, setZones] = useState<Zone[]>(cam.settings.zones ?? [])
  const [lines, setLines] = useState<Line[]>(cam.settings.lines ?? [])
  const [tool, setTool] = useState<Tool>('select')
  const [draft, setDraft] = useState<Pt[]>([])
  const [hover, setHover] = useState<Pt | null>(null)
  const [sel, setSel] = useState<Sel>(null)
  const [dims, setDims] = useState({ w: 960, h: 540 })
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [askDiscard, setAskDiscard] = useState(false)
  const requestClose = () => { if (dirty) setAskDiscard(true); else onClose() }
  const svgRef = useRef<SVGSVGElement>(null)
  const drag = useRef<{ kind: 'zone' | 'line'; id: string; idx: number } | null>(null)
  const { w, h } = dims

  const bg = useMemo(() => `${api.snapshotUrl(cam.id)}?raw=true&t=${Date.now()}`, [cam.id])
  const toN = (e: { clientX: number; clientY: number }): Pt => {
    const r = svgRef.current!.getBoundingClientRect()
    return [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)]
  }
  const touch = () => setDirty(true)

  const finishPolygon = (pts: Pt[]) => {
    if (pts.length < 3) return
    const z: Zone = {
      id: uid(), name: `Zone ${zones.length + 1}`, points: pts, classes: ['person'], color: COLORS[zones.length % COLORS.length],
      alert_on_enter: false, dwell_s: 0, max_occupancy: 0, require_helmet: false,
    }
    setZones((p) => [...p, z]); setSel({ kind: 'zone', id: z.id }); setDraft([]); setTool('select'); touch()
  }

  const onCanvasClick = (e: React.MouseEvent) => {
    if (readOnly || drag.current) return
    const p = toN(e)
    if (tool === 'polygon') {
      if (draft.length >= 3) {
        const [fx, fy] = draft[0]
        if (Math.hypot((p[0] - fx) * w, (p[1] - fy) * h) < 14) return finishPolygon(draft)
      }
      setDraft((d) => [...d, p])
    } else if (tool === 'line') {
      if (draft.length === 0) setDraft([p])
      else {
        const ln: Line = { id: uid(), name: `Line ${lines.length + 1}`, p1: draft[0], p2: p, classes: ['person'], alert: false }
        if (Math.abs(ln.p1[0] - ln.p2[0]) + Math.abs(ln.p1[1] - ln.p2[1]) < 0.02) return
        setLines((l) => [...l, ln]); setSel({ kind: 'line', id: ln.id }); setDraft([]); setTool('select'); touch()
      }
    } else setSel(null)
  }

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return
      if (e.key === 'Escape') { if (draft.length || tool !== 'select') { setDraft([]); setTool('select') } else onClose() }
      if (e.key === 'Enter' && tool === 'polygon') finishPolygon(draft)
      if (e.key === 'Backspace' && draft.length) setDraft((d) => d.slice(0, -1))
    }
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  })

  const startDrag = (kind: 'zone' | 'line', id: string, idx: number) => (e: React.PointerEvent) => {
    if (readOnly) return
    e.stopPropagation(); (e.target as Element).setPointerCapture(e.pointerId)
    drag.current = { kind, id, idx }
  }
  const onMove = (e: React.PointerEvent) => {
    const p = toN(e)
    setHover(p)
    const d = drag.current
    if (!d) return
    if (d.kind === 'zone') setZones((zs) => zs.map((z) => z.id === d.id ? { ...z, points: z.points.map((q, i) => i === d.idx ? p : q) } : z))
    else setLines((ls) => ls.map((l) => l.id === d.id ? (d.idx === 0 ? { ...l, p1: p } : { ...l, p2: p }) : l))
    touch()
  }
  const endDrag = () => { setTimeout(() => { drag.current = null }, 0) }

  const selZone = sel?.kind === 'zone' ? zones.find((z) => z.id === sel.id) : undefined
  const selLine = sel?.kind === 'line' ? lines.find((l) => l.id === sel.id) : undefined
  const upZone = (patch: Partial<Zone>) => { setZones((zs) => zs.map((z) => z.id === sel?.id ? { ...z, ...patch } : z)); touch() }
  const upLine = (patch: Partial<Line>) => { setLines((ls) => ls.map((l) => l.id === sel?.id ? { ...l, ...patch } : l)); touch() }
  const remove = () => {
    if (!sel) return
    if (sel.kind === 'zone') setZones((z) => z.filter((x) => x.id !== sel.id)); else setLines((l) => l.filter((x) => x.id !== sel.id))
    setSel(null); touch()
  }
  const toggleClass = (c: string, cur: string[], set: (v: string[]) => void) => {
    const next = cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c]
    if (next.length) set(next)
  }

  const save = async () => {
    setSaving(true)
    try { await api.patch(cam.id, { zones, lines }); setDirty(false); onClose() }
    catch (e) { onError((e as Error).message) } finally { setSaving(false) }
  }

  const px = (p: Pt) => `${p[0] * w},${p[1] * h}`
  const arrow = (l: Line) => {
    const [x1, y1, x2, y2] = [l.p1[0] * w, l.p1[1] * h, l.p2[0] * w, l.p2[1] * h]
    const n = Math.hypot(x2 - x1, y2 - y1) || 1
    const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
    return { mx, my, ax: mx - ((y2 - y1) / n) * 38, ay: my + ((x2 - x1) / n) * 38 }
  }

  return (
    <div className="overlay" onClick={requestClose}>
      <div className="expanded zone-editor" onClick={(e) => e.stopPropagation()}>
        <header>
          <h2>Zones &amp; lines · {cam.name}</h2>
          <button className="icon" onClick={requestClose}><X size={18} /></button>
        </header>
        <div className="expanded-main">
          <div>
            {!readOnly && (
              <div className="tools">
                <button className={tool === 'select' ? 'on' : ''} onClick={() => { setTool('select'); setDraft([]) }}><MousePointer2 size={15} />Select / edit</button>
                <button className={tool === 'polygon' ? 'on' : ''} onClick={() => { setTool('polygon'); setDraft([]); setSel(null) }}><Pentagon size={15} />Draw zone</button>
                <button className={tool === 'line' ? 'on' : ''} onClick={() => { setTool('line'); setDraft([]); setSel(null) }}><Minus size={15} />Draw line</button>
                <span className="hint">
                  {tool === 'polygon' ? 'Click to add corners · click the first point or press Enter to finish · Backspace undoes'
                    : tool === 'line' ? 'Click two points. The arrow marks the “in” direction.' : 'Click a shape to edit it · drag handles to reshape'}
                </span>
              </div>
            )}
            <div className="editor-canvas" style={{ aspectRatio: `${w} / ${h}` }}>
              <img src={bg} alt="" onLoad={(e) => setDims({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} draggable={false} />
              <svg ref={svgRef} viewBox={`0 0 ${w} ${h}`} onClick={onCanvasClick} onPointerMove={onMove} onPointerUp={endDrag}
                onMouseLeave={() => setHover(null)} className={tool !== 'select' ? 'drawing' : ''}>
                {zones.map((z) => (
                  <g key={z.id} onClick={(e) => { if (tool === 'select') { e.stopPropagation(); setSel({ kind: 'zone', id: z.id }) } }}>
                    <polygon points={z.points.map(px).join(' ')} fill={z.color} fillOpacity={sel?.id === z.id ? 0.32 : 0.2}
                      stroke={z.color} strokeWidth={sel?.id === z.id ? 4 : 2.5} />
                    <text x={Math.min(...z.points.map((p) => p[0])) * w + 6} y={Math.min(...z.points.map((p) => p[1])) * h + 20} className="zlabel" fill="#fff">{z.name}</text>
                    {sel?.id === z.id && !readOnly && z.points.map((p, i) => (
                      <circle key={i} cx={p[0] * w} cy={p[1] * h} r={8} className="handle" onPointerDown={startDrag('zone', z.id, i)} />
                    ))}
                  </g>
                ))}
                {lines.map((l) => {
                  const a = arrow(l)
                  return (
                    <g key={l.id} onClick={(e) => { if (tool === 'select') { e.stopPropagation(); setSel({ kind: 'line', id: l.id }) } }}>
                      <line x1={l.p1[0] * w} y1={l.p1[1] * h} x2={l.p2[0] * w} y2={l.p2[1] * h} stroke="transparent" strokeWidth={18} />
                      <line x1={l.p1[0] * w} y1={l.p1[1] * h} x2={l.p2[0] * w} y2={l.p2[1] * h} stroke="#3cc8ff" strokeWidth={sel?.id === l.id ? 5 : 3.5} strokeLinecap="round" />
                      <line x1={a.mx} y1={a.my} x2={a.ax} y2={a.ay} stroke="#3cc8ff" strokeWidth={3} markerEnd="url(#head)" />
                      <text x={l.p1[0] * w + 6} y={l.p1[1] * h - 8} className="zlabel" fill="#3cc8ff">{l.name}</text>
                      {sel?.id === l.id && !readOnly && ([l.p1, l.p2] as Pt[]).map((p, i) => (
                        <circle key={i} cx={p[0] * w} cy={p[1] * h} r={8} className="handle" onPointerDown={startDrag('line', l.id, i)} />
                      ))}
                    </g>
                  )
                })}
                <defs><marker id="head" markerWidth="8" markerHeight="8" refX="5" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#3cc8ff" /></marker></defs>
                {tool === 'polygon' && draft.length > 0 && (
                  <g>
                    <polyline points={[...draft, ...(hover ? [hover] : [])].map(px).join(' ')} fill="none" stroke="#fff" strokeWidth={2.5} strokeDasharray="6 5" />
                    {draft.map((p, i) => <circle key={i} cx={p[0] * w} cy={p[1] * h} r={i === 0 && draft.length >= 3 ? 9 : 5} fill="#fff" />)}
                  </g>
                )}
                {tool === 'line' && draft.length === 1 && hover && (
                  <line x1={draft[0][0] * w} y1={draft[0][1] * h} x2={hover[0] * w} y2={hover[1] * h} stroke="#fff" strokeWidth={2.5} strokeDasharray="6 5" />
                )}
              </svg>
            </div>
          </div>

          <aside>
            <h4>Shapes</h4>
            <ul className="shape-list">
              {zones.map((z) => (
                <li key={z.id} className={sel?.id === z.id ? 'on' : ''} onClick={() => setSel({ kind: 'zone', id: z.id })}>
                  <i style={{ background: z.color }} />{z.name}<small>zone</small>
                </li>
              ))}
              {lines.map((l) => (
                <li key={l.id} className={sel?.id === l.id ? 'on' : ''} onClick={() => setSel({ kind: 'line', id: l.id })}>
                  <i style={{ background: '#3cc8ff' }} />{l.name}<small>line</small>
                </li>
              ))}
              {zones.length + lines.length === 0 && <li className="muted">Nothing drawn yet</li>}
            </ul>

            {(selZone || selLine) && (
              <div className="props">
                <h4>{selZone ? 'Zone' : 'Line'} settings</h4>
                <label className="field">Name
                  <input value={(selZone ?? selLine)!.name} disabled={readOnly} maxLength={40}
                    onChange={(e) => selZone ? upZone({ name: e.target.value }) : upLine({ name: e.target.value })} />
                </label>
                <div className="field">Counts
                  <div className="class-pick">
                    {CLASSES.map((c) => {
                      const cur = (selZone ?? selLine)!.classes
                      return <button key={c} disabled={readOnly} className={cur.includes(c) ? 'on' : ''}
                        onClick={() => toggleClass(c, cur, (v) => selZone ? upZone({ classes: v }) : upLine({ classes: v }))}>{c}</button>
                    })}
                  </div>
                </div>
                {selZone && (
                  <>
                    <label className="toggle"><input type="checkbox" disabled={readOnly} checked={selZone.alert_on_enter} onChange={(e) => upZone({ alert_on_enter: e.target.checked })} />Alert on entry</label>
                    <label className="field">Alert if dwell longer than (seconds, 0 = off)
                      <input type="number" min={0} max={3600} disabled={readOnly} value={selZone.dwell_s} onChange={(e) => upZone({ dwell_s: Number(e.target.value) })} />
                    </label>
                    <label className="field">Alert if more than N inside (0 = off)
                      <input type="number" min={0} max={999} disabled={readOnly} value={selZone.max_occupancy} onChange={(e) => upZone({ max_occupancy: Number(e.target.value) })} />
                    </label>
                    <label className="toggle" title={cam.features.ppe_available ? '' : 'Needs a PPE model (backend/models/ppe.pt)'}>
                      <input type="checkbox" disabled={readOnly || !cam.features.ppe_available} checked={selZone.require_helmet} onChange={(e) => upZone({ require_helmet: e.target.checked })} />
                      Alert if a person has no helmet{!cam.features.ppe_available && <em> · needs PPE model</em>}
                    </label>
                  </>
                )}
                {selLine && (
                  <>
                    <label className="toggle"><input type="checkbox" disabled={readOnly} checked={selLine.alert} onChange={(e) => upLine({ alert: e.target.checked })} />Alert on every crossing</label>
                    {!readOnly && <button className="ghost" onClick={() => upLine({ p1: selLine.p2, p2: selLine.p1 })}>Flip “in” direction</button>}
                  </>
                )}
                {!readOnly && <button className="ghost danger" onClick={remove}><Trash2 size={14} />Delete</button>}
              </div>
            )}
            <p className="note">Foot point (bottom-centre of each box) is used for zone membership and line crossing. Shapes are stored per camera.</p>
            {!readOnly && <button className="primary wide" disabled={saving || !dirty} onClick={save}>{saving ? 'Saving…' : 'Save changes'}</button>}
          </aside>
        </div>
      </div>
      {askDiscard && (
        <ConfirmDialog title="Discard unsaved changes?" danger confirmLabel="Discard"
          message="Zones and lines you drew or moved since the last save will be lost."
          onCancel={() => setAskDiscard(false)} onConfirm={() => { setAskDiscard(false); onClose() }} />
      )}
    </div>
  )
}
