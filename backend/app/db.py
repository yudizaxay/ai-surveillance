"""Tiny SQLite layer for camera config and event metadata."""
import json
import sqlite3
import threading
import time

from .config import DB_PATH

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS cameras (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        source TEXT NOT NULL,
        settings TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        camera_id TEXT NOT NULL,
        camera_name TEXT NOT NULL,
        type TEXT NOT NULL,
        label TEXT,
        track_id INTEGER,
        confidence REAL,
        message TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
    CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS frames (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, camera_id TEXT NOT NULL,
        camera_name TEXT NOT NULL, thumb TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_frames_ts ON frames(ts DESC);
    CREATE TABLE IF NOT EXISTS frame_emb (
        frame_id INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT,
        x1 REAL, y1 REAL, x2 REAL, y2 REAL, emb BLOB NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_emb_frame ON frame_emb(frame_id);
    """
)

# lightweight migration: columns added after the first release
_existing = {r["name"] for r in _conn.execute("PRAGMA table_info(events)").fetchall()}
for _col, _ddl in {
    "severity": "TEXT NOT NULL DEFAULT 'info'",
    "ack": "INTEGER NOT NULL DEFAULT 0",
    "image": "TEXT",
    "clip": "TEXT",
    "zone": "TEXT",
}.items():
    if _col not in _existing:
        _conn.execute(f"ALTER TABLE events ADD COLUMN {_col} {_ddl}")
_conn.commit()


def save_camera(cam_id: str, name: str, kind: str, source: str, settings: dict) -> None:
    with _lock:
        _conn.execute(
            "INSERT OR REPLACE INTO cameras(id,name,kind,source,settings,created_at) VALUES(?,?,?,?,?,?)",
            (cam_id, name, kind, source, json.dumps(settings), time.time()),
        )
        _conn.commit()


def update_camera_settings(cam_id: str, settings: dict) -> None:
    with _lock:
        _conn.execute("UPDATE cameras SET settings=? WHERE id=?", (json.dumps(settings), cam_id))
        _conn.commit()


def delete_camera(cam_id: str) -> None:
    with _lock:
        _conn.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
        _conn.commit()


def load_cameras() -> list[dict]:
    with _lock:
        rows = _conn.execute("SELECT * FROM cameras ORDER BY created_at").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["settings"] = json.loads(d["settings"] or "{}")
        out.append(d)
    return out


def add_event(ev: dict) -> int:
    with _lock:
        cur = _conn.execute(
            "INSERT INTO events(ts,camera_id,camera_name,type,label,track_id,confidence,message,severity,image,clip,zone) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev["ts"], ev["camera_id"], ev["camera_name"], ev["type"],
                ev.get("label"), ev.get("track_id"), ev.get("confidence"), ev.get("message"),
                ev.get("severity", "info"), ev.get("image"), ev.get("clip"), ev.get("zone"),
            ),
        )
        _conn.commit()
        return cur.lastrowid


def list_events(limit: int = 100, camera_id: str | None = None, severity: str | None = None) -> list[dict]:
    q = "SELECT * FROM events"
    where, args = [], []
    if camera_id:
        where.append("camera_id=?")
        args.append(camera_id)
    if severity:
        where.append("severity=?")
        args.append(severity)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with _lock:
        return [dict(r) for r in _conn.execute(q, args).fetchall()]


def events_since(since: float, limit: int = 20000) -> list[dict]:
    with _lock:
        rows = _conn.execute("SELECT * FROM events WHERE ts>=? ORDER BY ts DESC LIMIT ?", (since, limit)).fetchall()
    return [dict(r) for r in rows]


def event_summary() -> list[dict]:
    with _lock:
        rows = _conn.execute(
            "SELECT camera_name, label, COUNT(*) AS n FROM events WHERE type='new_track' GROUP BY camera_name, label ORDER BY camera_name, label"
        ).fetchall()
    return [dict(r) for r in rows]


def ack_alert(event_id: int | None = None) -> int:
    """Acknowledge one alert, or all when event_id is None. Returns rows changed."""
    with _lock:
        if event_id is None:
            cur = _conn.execute("UPDATE events SET ack=1 WHERE severity='alert' AND ack=0")
        else:
            cur = _conn.execute("UPDATE events SET ack=1 WHERE id=? AND severity='alert'", (event_id,))
        _conn.commit()
        return cur.rowcount


def unacked_alerts() -> int:
    with _lock:
        return _conn.execute("SELECT COUNT(*) FROM events WHERE severity='alert' AND ack=0").fetchone()[0]


def get_kv(key: str, default: str = "") -> str:
    with _lock:
        r = _conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_kv(key: str, value: str) -> None:
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)", (key, value))
        _conn.commit()


# ------------------------------------------------------------- search index
def add_frame(ts: float, cam_id: str, cam_name: str, thumb: str, embs: list[tuple]) -> int:
    """embs: (kind, label, x1, y1, x2, y2, float16 bytes) rows for this frame."""
    with _lock:
        cur = _conn.execute("INSERT INTO frames(ts,camera_id,camera_name,thumb) VALUES(?,?,?,?)", (ts, cam_id, cam_name, thumb))
        fid = cur.lastrowid
        _conn.executemany("INSERT INTO frame_emb(frame_id,kind,label,x1,y1,x2,y2,emb) VALUES(?,?,?,?,?,?,?,?)",
                          [(fid, *e) for e in embs])
        _conn.commit()
        return fid


def prune_frames(keep: int) -> list[str]:
    """Delete the oldest indexed frames beyond `keep`; returns their thumbnail names so files can be removed."""
    with _lock:
        rows = _conn.execute("SELECT id, thumb FROM frames ORDER BY id DESC LIMIT -1 OFFSET ?", (keep,)).fetchall()
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        marks = ",".join("?" * len(ids))
        _conn.execute(f"DELETE FROM frame_emb WHERE frame_id IN ({marks})", ids)
        _conn.execute(f"DELETE FROM frames WHERE id IN ({marks})", ids)
        _conn.commit()
        return [r["thumb"] for r in rows]


def clear_index(camera_id: str | None = None) -> list[str]:
    with _lock:
        where, args = ("WHERE camera_id=?", (camera_id,)) if camera_id else ("", ())
        rows = _conn.execute(f"SELECT id, thumb FROM frames {where}", args).fetchall()
        ids = [r["id"] for r in rows]
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            marks = ",".join("?" * len(chunk))
            _conn.execute(f"DELETE FROM frame_emb WHERE frame_id IN ({marks})", chunk)
            _conn.execute(f"DELETE FROM frames WHERE id IN ({marks})", chunk)
        _conn.commit()
        return [r["thumb"] for r in rows]


def index_rows(since: float = 0.0, camera_id: str | None = None) -> list[sqlite3.Row]:
    q = ("SELECT e.frame_id, e.kind, e.label, e.x1, e.y1, e.x2, e.y2, e.emb, f.ts, f.camera_id, f.camera_name, f.thumb "
         "FROM frame_emb e JOIN frames f ON f.id = e.frame_id WHERE f.ts >= ?")
    args: list = [since]
    if camera_id:
        q += " AND f.camera_id = ?"
        args.append(camera_id)
    with _lock:
        return _conn.execute(q, args).fetchall()


def index_stats() -> dict:
    with _lock:
        n = _conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
        span = _conn.execute("SELECT MIN(ts), MAX(ts) FROM frames").fetchone()
    return {"frames": n, "oldest": span[0], "newest": span[1]}
