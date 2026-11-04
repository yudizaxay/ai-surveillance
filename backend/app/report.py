"""Self-contained HTML activity report (print to PDF from the browser). No extra dependencies."""
from __future__ import annotations

import base64
import time
from collections import Counter, defaultdict
from html import escape

from .config import CATEGORIES, MEDIA_DIR

LABELS = {
    "line_cross": "Line crossed", "zone_enter": "Zone entry", "zone_exit": "Zone exit", "dwell": "Dwell time",
    "capacity": "Over capacity", "fall": "Possible fall", "ppe_violation": "No helmet", "visibility": "Low visibility",
    "camera_tamper": "Camera tampering", "camera_reconnecting": "Camera reconnecting", "camera_error": "Camera error",
}


def _thumb(name: str | None) -> str:
    if not name or "/" in name or "\\" in name or not name.endswith(".jpg"):
        return ""
    p = MEDIA_DIR / name
    try:
        if p.is_file() and p.stat().st_size < 400_000:
            return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
    except OSError:
        pass
    return ""


def _bars(values: list[int], labels: list[str], color: str = "#3ddc84") -> str:
    W, H, pad = 720, 150, 22
    mx = max(values + [1])
    bw = (W - 2 * pad) / max(len(values), 1)
    out = [f'<svg viewBox="0 0 {W} {H + 22}" class="chart" role="img" aria-label="Activity per hour">']
    for i, v in enumerate(values):
        h = (v / mx) * (H - 20)
        x = pad + i * bw
        out.append(f'<rect x="{x + 2:.1f}" y="{H - h:.1f}" width="{max(bw - 4, 1):.1f}" height="{h:.1f}" rx="2" fill="{color}"><title>{escape(labels[i])}: {v}</title></rect>')
        if i % max(1, len(values) // 12) == 0:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{H + 15}" text-anchor="middle" font-size="10" fill="#6b7785">{escape(labels[i])}</text>')
    out.append(f'<text x="{pad - 6}" y="12" text-anchor="end" font-size="10" fill="#6b7785">{mx}</text></svg>')
    return "".join(out)


def build(events: list[dict], hours: int, cameras: list[dict]) -> str:
    now = time.time()
    since = now - hours * 3600
    tracks = [e for e in events if e["type"] == "new_track"]
    alerts = [e for e in events if e.get("severity") == "alert"]
    unacked = sum(1 for e in alerts if not e.get("ack"))

    per_cam: dict[str, Counter] = defaultdict(Counter)
    for e in tracks:
        per_cam[e["camera_name"]][e["label"] or "object"] += 1
    cats = [c for c in CATEGORIES if any(per_cam[k][c] for k in per_cam)]

    hour_vals, hour_labels = [], []
    start = int(since // 3600) * 3600
    buckets = Counter(int((e["ts"] - start) // 3600) for e in tracks)
    for i in range(hours + 1):
        hour_vals.append(buckets.get(i, 0))
        hour_labels.append(time.strftime("%H:%M", time.localtime(start + i * 3600)))
    peak = max(range(len(hour_vals)), key=lambda i: hour_vals[i]) if any(hour_vals) else None

    by_type = Counter(LABELS.get(e["type"], e["type"]) for e in alerts)
    health = Counter(e["type"] for e in events if e["type"] in ("camera_tamper", "camera_reconnecting", "camera_error", "visibility"))

    rows = "".join(
        f"<tr><td>{escape(cam)}</td>" + "".join(f"<td>{per_cam[cam][c] or '–'}</td>" for c in cats) + f"<td><b>{sum(per_cam[cam].values())}</b></td></tr>"
        for cam in sorted(per_cam)
    ) or f'<tr><td colspan="{len(cats) + 2}" class="muted">No detections in this period</td></tr>'
    head = "".join(f"<th>{escape(c.title())}</th>" for c in cats)
    type_rows = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in by_type.most_common()) or '<tr><td colspan="2" class="muted">No alerts</td></tr>'

    cards = []
    for e in alerts[:6]:
        img = _thumb(e.get("image"))
        cards.append(
            f'<figure>{f"<img src={chr(34)}{img}{chr(34)} alt={chr(34)}alert snapshot{chr(34)}>" if img else "<div class=noimg>no snapshot</div>"}'
            f'<figcaption><b>{escape(LABELS.get(e["type"], e["type"]))}</b> · {escape(e["camera_name"])}<br>'
            f'<span>{time.strftime("%d %b %H:%M", time.localtime(e["ts"]))}</span><br>{escape(e.get("message") or "")}</figcaption></figure>')

    period = f'{time.strftime("%d %b %Y %H:%M", time.localtime(since))} – {time.strftime("%d %b %Y %H:%M", time.localtime(now))}'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vision Monitor report</title><style>
:root{{--bg:#fff;--fg:#14202b;--mut:#6b7785;--line:#dde3ea;--acc:#0f9d58}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:var(--fg);background:var(--bg)}}
main{{max-width:900px;margin:0 auto;padding:28px 24px 48px}}
header{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:2px solid var(--acc);padding-bottom:12px;margin-bottom:20px}}
h1{{margin:0;font-size:22px}}h2{{font-size:15px;margin:26px 0 8px}}.sub{{color:var(--mut);font-size:13px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.kpi{{border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.kpi b{{display:block;font-size:24px}}.kpi span{{color:var(--mut);font-size:12px}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}th{{font-size:12px;color:var(--mut);font-weight:600}}
.chart{{width:100%;height:auto}}.muted{{color:var(--mut)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}figure{{margin:0;border:1px solid var(--line);border-radius:10px;overflow:hidden}}
figure img{{width:100%;display:block}}.noimg{{padding:30px;text-align:center;color:var(--mut);background:#f3f5f8}}figcaption{{padding:8px 10px;font-size:12px}}figcaption span{{color:var(--mut)}}
button{{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer}}
.note{{color:var(--mut);font-size:12px;margin-top:24px}}
@media print{{button{{display:none}}main{{padding:0}}figure,tr,.kpi{{break-inside:avoid}}}}
@media (max-width:640px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><div><h1>Vision Monitor · Activity report</h1><div class="sub">{escape(period)} ({hours} h) · generated {time.strftime("%d %b %Y %H:%M")}</div></div>
<button onclick="window.print()">Print / Save as PDF</button></header>
<div class="kpis">
<div class="kpi"><b>{len(tracks)}</b><span>Objects tracked</span></div>
<div class="kpi"><b>{len(alerts)}</b><span>Alerts ({unacked} open)</span></div>
<div class="kpi"><b>{len(per_cam)}</b><span>Cameras with detections</span></div>
<div class="kpi"><b>{escape(hour_labels[peak]) if peak is not None else "–"}</b><span>Busiest hour</span></div></div>
<h2>Activity per hour</h2>{_bars(hour_vals, hour_labels)}
<h2>Detections by camera</h2><table><tr><th>Camera</th>{head}<th>Total</th></tr>{rows}</table>
<h2>Alerts by type</h2><table><tr><th>Type</th><th>Count</th></tr>{type_rows}</table>
<h2>Camera health and visibility</h2>
<table><tr><td>Tamper alerts</td><td>{health["camera_tamper"]}</td></tr><tr><td>Reconnects</td><td>{health["camera_reconnecting"]}</td></tr>
<tr><td>Camera errors</td><td>{health["camera_error"]}</td></tr><tr><td>Low-visibility events (fog / haze)</td><td>{health["visibility"]}</td></tr></table>
{f'<h2>Latest alerts</h2><div class="grid">{"".join(cards)}</div>' if cards else ""}
<p class="note">“Objects tracked” counts distinct tracker IDs, which can overcount when an object is lost and re-acquired. Alerts marked as possible falls need human review. Generated from {len(cameras)} configured camera(s).</p>
</main></body></html>"""
