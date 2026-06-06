"""Explicit per-client session state for Hybrid FTP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEMO_USERS = {"student": "cs494"}


@dataclass
class Session:
    """State owned by one TCP control session."""

    session_id: int
    client_address: tuple[str, int]
    server_root: Path
    username: str | None = None
    pending_username: str | None = None
    authenticated: bool = False
    cwd: PurePosixPath = PurePosixPath("/")
    state: str = "connected"
