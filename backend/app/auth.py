"""Optional login with two roles. Auth is OFF unless VM_ADMIN_PASSWORD is set.

  VM_ADMIN_USER (default "admin") + VM_ADMIN_PASSWORD   -> full control
  VM_VIEWER_USER (default "viewer") + VM_VIEWER_PASSWORD -> read-only (GET requests only)

Sessions are HMAC-signed, HttpOnly cookies. This is intentionally small: put the service behind HTTPS
(reverse proxy) before exposing it beyond a trusted network.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from .config import DATA_DIR

COOKIE = "vm_session"
TTL = 12 * 3600

ADMIN_USER = os.getenv("VM_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("VM_ADMIN_PASSWORD", "")
VIEWER_USER = os.getenv("VM_VIEWER_USER", "viewer")
VIEWER_PASSWORD = os.getenv("VM_VIEWER_PASSWORD", "")

ENABLED = bool(ADMIN_PASSWORD)

_secret_file = DATA_DIR / ".secret"
if not _secret_file.exists():
    _secret_file.write_text(secrets.token_hex(32))
    _secret_file.chmod(0o600)
_SECRET = _secret_file.read_text().strip().encode()

_failures: dict[str, list[float]] = {}


def _sign(payload: str) -> str:
    return hmac.new(_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(user: str, role: str) -> str:
    payload = f"{user}|{role}|{int(time.time()) + TTL}"
    return base64.urlsafe_b64encode(payload.encode()).decode() + "." + _sign(payload)


def verify_token(token: str | None) -> tuple[str, str] | None:
    if not token or "." not in token:
        return None
    try:
        b64, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(b64.encode()).decode()
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        user, role, exp = payload.split("|")
        if int(exp) < time.time():
            return None
        return user, role
    except Exception:
        return None


def too_many_attempts(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(ip, []) if now - t < 60]
    _failures[ip] = recent
    return len(recent) >= 5


def check_login(ip: str, username: str, password: str) -> str | None:
    """Returns the role on success, else None (and records the failure)."""
    for user, pw, role in ((ADMIN_USER, ADMIN_PASSWORD, "admin"), (VIEWER_USER, VIEWER_PASSWORD, "viewer")):
        if pw and hmac.compare_digest(username, user) and hmac.compare_digest(password, pw):
            _failures.pop(ip, None)
            return role
    _failures.setdefault(ip, []).append(time.time())
    return None
