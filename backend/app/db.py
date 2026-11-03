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
