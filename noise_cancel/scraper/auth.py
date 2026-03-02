from __future__ import annotations

import json
import time
from pathlib import Path

from cryptography.fernet import Fernet


def generate_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_session(storage_state: dict, key: str) -> bytes:
    f = Fernet(key.encode() if isinstance(key, str) else key)
    plaintext = json.dumps(storage_state).encode()
    return f.encrypt(plaintext)


def decrypt_session(encrypted: bytes, key: str) -> dict:
    f = Fernet(key.encode() if isinstance(key, str) else key)
    plaintext = f.decrypt(encrypted)
    return json.loads(plaintext)


def save_session(storage_state: dict, key: str, path: str) -> None:
    encrypted = encrypt_session(storage_state, key)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(encrypted)


def load_session(key: str, path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    encrypted = p.read_bytes()
    return decrypt_session(encrypted, key)


def is_session_valid(path: str, ttl_days: int = 7) -> bool:
    p = Path(path)
    if not p.exists():
        return False
    mtime = p.stat().st_mtime
    age_seconds = time.time() - mtime
    return age_seconds < ttl_days * 86400


def validate_session(*, key_path: str, session_path: str, ttl_days: int = 7) -> dict:
    key_file = Path(key_path)
    session_file = Path(session_path)

    if not session_file.exists() or not key_file.exists():
        msg = "No session found. Run login first."
        raise RuntimeError(msg)

    if not is_session_valid(str(session_file), ttl_days=ttl_days):
        msg = "Session expired. Run login to refresh."
        raise RuntimeError(msg)

    key = key_file.read_text().strip()
    session_data = load_session(key, str(session_file))
    if session_data is None:
        msg = "Failed to decrypt session. Run login again."
        raise RuntimeError(msg)
    return session_data
