"""Explicit per-client session state for Hybrid FTP."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from threading import Event, RLock, Thread

from .data_channel import Endpoint

DEMO_USERS = {"student": "cs494"}


@dataclass
class TransferState:
    """Mutable per-session state for one UDP transfer."""

    transfer_id: int | None = None
    direction: str = "idle"
    cancel: Event = field(default_factory=Event)
    lock: RLock = field(default_factory=RLock)
    udp_socket: socket.socket | None = None
    bytes_transferred: int = 0
    sha256: str | None = None
    worker: Thread | None = None

    def close_socket(self) -> None:
        if self.udp_socket is not None:
            self.udp_socket.close()
            self.udp_socket = None

    def begin(self, transfer_id: int, direction: str, udp_socket: socket.socket) -> None:
        self.transfer_id = transfer_id
        self.direction = direction
        self.cancel = Event()
        self.udp_socket = udp_socket
        self.bytes_transferred = 0
        self.sha256 = None
        self.worker = None

    def finish(self) -> None:
        self.close_socket()
        self.direction = "idle"
        self.worker = None


@dataclass(frozen=True)
class TransferRequest:
    """A validated data-transfer job awaiting execution after a 150 reply."""

    direction: str
    source: Path | None = None
    destination: Path | None = None
    append_to: Path | None = None
    display_path: str = ""


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
    rename_from_real: Path | None = None
    rename_from_virtual: PurePosixPath | None = None
    transfer_type: str = "I"
    transfer_mode: str = "S"
    data_mode: str = "NONE"
    active_endpoint: Endpoint | None = None
    passive_endpoint: Endpoint | None = None
    transfer: TransferState = field(default_factory=TransferState)
    pending_transfer: TransferRequest | None = None
    reply_lock: RLock = field(default_factory=RLock)
    state: str = "connected"
