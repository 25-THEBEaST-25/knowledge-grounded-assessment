"""Isolated local file-storage adapter. Only metadata/paths go in PostgreSQL."""
import os
from pathlib import Path


def root() -> Path:
    p = Path(os.getenv("STORAGE_DIR", "./storage")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def save(namespace: str, sha256: str, filename: str, content: bytes) -> str:
    safe = "".join(ch for ch in os.path.basename(filename) if ch.isalnum() or ch in "._-") or "file"
    rel = Path(namespace) / f"{sha256[:16]}_{safe}"
    full = root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)
    return str(rel)


def read(rel_path: str) -> bytes:
    full = (root() / rel_path).resolve()
    if root() not in full.parents:  # no path traversal out of the storage root
        raise ValueError("invalid storage path")
    return full.read_bytes()
