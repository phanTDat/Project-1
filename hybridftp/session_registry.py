"""Lock-protected visibility for concurrent Hybrid FTP control sessions."""

from __future__ import annotations

from threading import RLock

from .filesystem import virtual_to_text
from .session import Session


class SessionRegistry:
    """Maintain a safe snapshot of connected sessions for STAT evidence."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[int, Session] = {}

    def add(self, session: Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def remove(self, session_id: int) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def status_lines(self) -> list[str]:
        with self._lock:
            sessions = list(self._sessions.values())
        if not sessions:
            return ["active_sessions=0"]
        lines = [f"active_sessions={len(sessions)}"]
        for item in sorted(sessions, key=lambda session: session.session_id):
            endpoint = item.passive_endpoint or item.active_endpoint
            endpoint_text = f"{endpoint.host}:{endpoint.port}" if endpoint else "none"
            lines.append(
                "session="
                f"{item.session_id} client={item.client_address[0]}:{item.client_address[1]} "
                f"auth={item.authenticated} cwd={virtual_to_text(item.cwd)} "
                f"data_mode={item.data_mode} endpoint={endpoint_text} "
                f"transfer={item.transfer.direction} bytes={item.transfer.bytes_transferred}"
            )
        return lines
