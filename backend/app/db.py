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
    """
)


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
            "INSERT INTO events(ts,camera_id,camera_name,type,label,track_id,confidence,message) VALUES(?,?,?,?,?,?,?,?)",
            (
                ev["ts"], ev["camera_id"], ev["camera_name"], ev["type"],
                ev.get("label"), ev.get("track_id"), ev.get("confidence"), ev.get("message"),
            ),
        )
        _conn.commit()
        return cur.lastrowid


def list_events(limit: int = 100, camera_id: str | None = None) -> list[dict]:
    q = "SELECT * FROM events"
    args: list = []
    if camera_id:
        q += " WHERE camera_id=?"
        args.append(camera_id)
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
