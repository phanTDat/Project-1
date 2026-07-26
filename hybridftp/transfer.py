"""Selective-repeat reliable UDP sender and receiver for Hybrid FTP.

The routines are deliberately synchronous and small: the server gives each
transfer its own worker, while this module keeps only a bounded packet window in
flight.  Payload bytes move only through UDP sockets, never the TCP control
connection.
"""

from __future__ import annotations

import hashlib
import os
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable

from .rdt import (
    DEFAULT_WINDOW,
    FLAG_ABORT,
    FLAG_ACK,
    FLAG_DATA,
    FLAG_FIN,
    FLAG_FIN_ACK,
    MAX_PAYLOAD,
    Packet,
    PacketError,
    abort_packet,
    ack_packet,
    data_packet,
    fin_ack_packet,
    fin_packet,
)

TIMEOUT_SECONDS = 0.20
MAX_RETRIES = 12
RECEIVE_BUFFER = 2048


class TransferError(RuntimeError):
    """A transfer failed before verified completion."""


class TransferAborted(TransferError):
    """A transfer was cancelled by ABOR or local shutdown."""


@dataclass(frozen=True)
class TransferResult:
    transfer_id: int
    bytes_transferred: int
    sha256: str
    packets: int
    retransmissions: int = 0


Log = Callable[[str], None]


def _emit(log: Log | None, message: str) -> None:
    if log is not None:
        log(message)


def _cancelled(cancel: Event | None) -> bool:
    return cancel is not None and cancel.is_set()


def send_file(
    sock: socket.socket,
    peer: tuple[str, int] | None,
    source: Path,
    transfer_id: int,
    *,
    window_size: int = DEFAULT_WINDOW,
    timeout: float = TIMEOUT_SECONDS,
    cancel: Event | None = None,
    log: Log | None = None,
) -> TransferResult:
    """Send a binary file using an ACKed bounded sliding window.

    In passive RETR the server does not know the client's UDP source port until
    it receives the client's ready ACK, so ``peer`` may be ``None``.
    """

    if not source.is_file():
        raise TransferError("transfer source is not a regular file")
    if not 1 <= window_size <= 0xFFFF:
        raise TransferError("invalid transfer window")
    original_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    digest = hashlib.sha256()
    bytes_sent = packets_sent = retransmissions = 0
    next_sequence = base = 0
    eof = False
    # sequence -> [packet, last send time, retransmission count]
    in_flight: dict[int, list[object]] = {}
    try:
        if peer is None:
            peer = _wait_for_ready(sock, transfer_id, cancel, log)
        with source.open("rb") as stream:
            while not eof or in_flight:
                if _cancelled(cancel):
                    _send_abort(sock, peer, transfer_id)
                    raise TransferAborted("transfer cancelled")
                while not eof and next_sequence < base + window_size:
                    payload = stream.read(MAX_PAYLOAD)
                    if not payload:
                        eof = True
                        break
                    packet = data_packet(transfer_id, next_sequence, payload, window_size)
                    sock.sendto(packet.encode(), peer)
                    in_flight[next_sequence] = [packet, time.monotonic(), 0]
                    digest.update(payload)
                    bytes_sent += len(payload)
                    packets_sent += 1
                    _emit(log, f"rdt send id={transfer_id} seq={next_sequence} window={base}:{base + window_size - 1}")
                    next_sequence += 1
                if not in_flight:
                    continue
                try:
                    raw, address = sock.recvfrom(RECEIVE_BUFFER)
                except socket.timeout:
                    retransmissions += _retransmit_expired(sock, peer, in_flight, timeout, transfer_id, log)
                    continue
                if address != peer:
                    continue
                try:
                    packet = Packet.decode(raw)
                except PacketError:
                    continue
                if packet.transfer_id != transfer_id:
                    continue
                if packet.flags == FLAG_ABORT:
                    raise TransferAborted("remote peer aborted transfer")
                if packet.flags != FLAG_ACK:
                    continue
                if packet.acknowledgement in in_flight:
                    del in_flight[packet.acknowledgement]
                    _emit(log, f"rdt ack id={transfer_id} ack={packet.acknowledgement} advertised_window={packet.window}")
                    while base < next_sequence and base not in in_flight:
                        base += 1
                        _emit(log, f"rdt window advance id={transfer_id} base={base}")

        fin_sequence = next_sequence
        fin = fin_packet(transfer_id, fin_sequence)
        for attempt in range(1, MAX_RETRIES + 1):
            if _cancelled(cancel):
                _send_abort(sock, peer, transfer_id)
                raise TransferAborted("transfer cancelled")
            sock.sendto(fin.encode(), peer)
            _emit(log, f"rdt fin id={transfer_id} seq={fin_sequence} attempt={attempt}")
            try:
                while True:
                    raw, address = sock.recvfrom(RECEIVE_BUFFER)
                    if address != peer:
                        continue
                    response = Packet.decode(raw)
                    if response.transfer_id != transfer_id:
                        continue
                    if response.flags == FLAG_ABORT:
                        raise TransferAborted("remote peer aborted transfer")
                    if response.flags == FLAG_FIN_ACK and response.acknowledgement == fin_sequence:
                        return TransferResult(transfer_id, bytes_sent, digest.hexdigest(), packets_sent, retransmissions)
            except socket.timeout:
                retransmissions += 1
        raise TransferError("FIN acknowledgement timed out")
    finally:
        sock.settimeout(original_timeout)


def receive_file(
    sock: socket.socket,
    peer: tuple[str, int] | None,
    destination: Path,
    transfer_id: int,
    *,
    window_size: int = DEFAULT_WINDOW,
    timeout: float = TIMEOUT_SECONDS,
    cancel: Event | None = None,
    send_ready: bool = False,
    log: Log | None = None,
) -> TransferResult:
    """Receive an ordered transfer into a temp file, then atomically rename it."""

    if not 1 <= window_size <= 0xFFFF:
        raise TransferError("invalid transfer window")
    if send_ready and peer is None:
        raise TransferError("receiver needs a passive sender endpoint")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{transfer_id:016x}.part")
    if temporary.exists():
        temporary.unlink()
    original_timeout = sock.gettimeout()
    sock.settimeout(timeout)
    expected = 0
    buffered: dict[int, bytes] = {}
    digest = hashlib.sha256()
    bytes_received = packets = idle_timeouts = 0
    discovered_peer = peer
    try:
        if send_ready:
            _send_ack(sock, discovered_peer, transfer_id, 0, window_size)
            _emit(log, f"rdt ready id={transfer_id}")
        completed = False
        with temporary.open("wb") as stream:
            while not completed:
                if _cancelled(cancel):
                    if discovered_peer is not None:
                        _send_abort(sock, discovered_peer, transfer_id)
                    raise TransferAborted("transfer cancelled")
                try:
                    raw, address = sock.recvfrom(RECEIVE_BUFFER)
                except socket.timeout:
                    idle_timeouts += 1
                    if idle_timeouts >= MAX_RETRIES:
                        raise TransferError("data packets timed out")
                    if discovered_peer is not None:
                        _send_ack(sock, discovered_peer, transfer_id, max(0, expected - 1), max(0, window_size - len(buffered)))
                    continue
                idle_timeouts = 0
                if discovered_peer is not None and address != discovered_peer:
                    continue
                try:
                    packet = Packet.decode(raw)
                except PacketError:
                    continue
                if packet.transfer_id != transfer_id:
                    continue
                if discovered_peer is None:
                    discovered_peer = address
                if packet.flags == FLAG_ABORT:
                    raise TransferAborted("remote peer aborted transfer")
                if packet.flags == FLAG_FIN:
                    if packet.sequence != expected:
                        _send_ack(sock, discovered_peer, transfer_id, max(0, expected - 1), window_size - len(buffered))
                        continue
                    sock.sendto(fin_ack_packet(transfer_id, packet.sequence).encode(), discovered_peer)
                    stream.flush()
                    os.fsync(stream.fileno())
                    completed = True
                    continue
                if packet.flags != FLAG_DATA:
                    continue
                sequence = packet.sequence
                if sequence < expected:
                    _send_ack(sock, discovered_peer, transfer_id, sequence, window_size - len(buffered))
                    continue
                if sequence >= expected + window_size:
                    _send_ack(sock, discovered_peer, transfer_id, max(0, expected - 1), window_size - len(buffered))
                    continue
                if sequence not in buffered:
                    buffered[sequence] = packet.payload
                    packets += 1
                _send_ack(sock, discovered_peer, transfer_id, sequence, window_size - len(buffered))
                _emit(log, f"rdt receive id={transfer_id} seq={sequence} expected={expected} buffered={len(buffered)}")
                while expected in buffered:
                    payload = buffered.pop(expected)
                    stream.write(payload)
                    digest.update(payload)
                    bytes_received += len(payload)
                    expected += 1
                    _emit(log, f"rdt window drain id={transfer_id} next={expected}")
        temporary.replace(destination)
        return TransferResult(transfer_id, bytes_received, digest.hexdigest(), packets)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise
    finally:
        sock.settimeout(original_timeout)


def _wait_for_ready(sock: socket.socket, transfer_id: int, cancel: Event | None, log: Log | None) -> tuple[str, int]:
    for _ in range(MAX_RETRIES):
        if _cancelled(cancel):
            raise TransferAborted("transfer cancelled")
        try:
            raw, address = sock.recvfrom(RECEIVE_BUFFER)
            packet = Packet.decode(raw)
        except socket.timeout:
            continue
        except PacketError:
            continue
        if packet.transfer_id == transfer_id and packet.flags == FLAG_ACK:
            _emit(log, f"rdt passive peer ready id={transfer_id} peer={address[0]}:{address[1]}")
            return address
    raise TransferError("passive receiver did not send a ready acknowledgement")


def _send_ack(sock: socket.socket, peer: tuple[str, int], transfer_id: int, acknowledgement: int, window: int) -> None:
    sock.sendto(ack_packet(transfer_id, acknowledgement, max(0, window)).encode(), peer)


def _send_abort(sock: socket.socket, peer: tuple[str, int], transfer_id: int) -> None:
    try:
        sock.sendto(abort_packet(transfer_id).encode(), peer)
    except OSError:
        pass


def _retransmit_expired(
    sock: socket.socket,
    peer: tuple[str, int],
    in_flight: dict[int, list[object]],
    timeout: float,
    transfer_id: int,
    log: Log | None,
) -> int:
    now = time.monotonic()
    retransmissions = 0
    for sequence, state in list(in_flight.items()):
        packet, sent_at, retries = state
        assert isinstance(packet, Packet)
        assert isinstance(sent_at, float)
        assert isinstance(retries, int)
        if now - sent_at < timeout:
            continue
        if retries >= MAX_RETRIES:
            raise TransferError(f"packet {sequence} retry limit exceeded")
        sock.sendto(packet.encode(), peer)
        in_flight[sequence] = [packet, now, retries + 1]
        retransmissions += 1
        _emit(log, f"rdt retransmit id={transfer_id} seq={sequence} retry={retries + 1}")
    return retransmissions
