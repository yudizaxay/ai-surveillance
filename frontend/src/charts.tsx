export interface Series { name: string; color: string; values: number[] }

const fmtT = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

/** Dependency-free responsive SVG line chart. */
export function LineChart({
  times, series, height = 170, unit = '',
}: { times: number[]; series: Series[]; height?: number; unit?: string }) {
  const W = 640, H = height, L = 34, R = 10, T = 10, B = 22
  const n = times.length
  const max = Math.max(1, ...series.flatMap((s) => s.values))
  const niceMax = max <= 4 ? 4 : Math.ceil(max / 4) * 4
  const x = (i: number) => L + (n <= 1 ? 0 : (i / (n - 1)) * (W - L - R))
  const y = (v: number) => T + (1 - v / niceMax) * (H - T - B)
  const ticks = [0, 0.5, 1].map((f) => Math.round(niceMax * f))

  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" preserveAspectRatio="xMidYMid meet">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} className="gridline" />
            <text x={L - 6} y={y(t) + 4} textAnchor="end" className="axis">{t}</text>
          </g>
        ))}
        {n > 1 && [0, Math.floor((n - 1) / 2), n - 1].map((i) => (
          <text key={i} x={x(i)} y={H - 5} textAnchor={i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle'} className="axis">{fmtT(times[i])}</text>
        ))}
        {series.map((s) => n > 1 && (
          <g key={s.name}>
            <path d={`M${s.values.map((v, i) => `${x(i)},${y(v)}`).join(' L')} L${x(n - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={s.color} opacity=".1" />
            <polyline points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          </g>
        ))}
        {n <= 1 && <text x={W / 2} y={H / 2} textAnchor="middle" className="axis">Collecting data…</text>}
      </svg>
      <div className="legend">
        {series.map((s) => (
          <span key={s.name}><i style={{ background: s.color }} />{s.name}
            <b>{s.values.length ? s.values[s.values.length - 1] : 0}{unit}</b></span>
        ))}
      </div>
    </div>
  )
}

export function Donut({ parts, size = 132 }: { parts: { name: string; value: number; color: string }[]; size?: number }) {
  const total = parts.reduce((a, p) => a + p.value, 0)
  const r = 46, c = 2 * Math.PI * r
  let acc = 0
  return (
    <div className="donut">
      <svg viewBox="0 0 120 120" width={size} height={size} role="img">
        <circle cx="60" cy="60" r={r} fill="none" stroke="var(--panel-2)" strokeWidth="14" />
        {total > 0 && parts.filter((p) => p.value > 0).map((p) => {
          const len = (p.value / total) * c
          const el = <circle key={p.name} cx="60" cy="60" r={r} fill="none" stroke={p.color} strokeWidth="14"
            strokeDasharray={`${Math.max(len - 1.5, 0)} ${c}`} strokeDashoffset={-acc} transform="rotate(-90 60 60)" />
          acc += len
          return el
        })}
        <text x="60" y="58" textAnchor="middle" className="donut-n">{total}</text>
        <text x="60" y="73" textAnchor="middle" className="axis">unique</text>
      </svg>
      <ul>
        {parts.map((p) => (
          <li key={p.name}><i style={{ background: p.color }} />{p.name}<b>{p.value}</b></li>
        ))}
      </ul>
    </div>
  )
}
