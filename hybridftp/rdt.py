"""Custom reliable-UDP packet format for Hybrid FTP data transfers.

The fixed 32-byte network-order header is deliberately small enough to explain in
an oral defense.  TCP carries only FTP commands/replies; this module carries the
file bytes over UDP.

    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-------------------------------+-------+-------+---------------+
   | magic: HFTP (32)              | ver   | flags | header length |
   +-------------------------------+-------+-------+---------------+
   | transfer id (64)                                              |
   +---------------------------------------------------------------+
   | sequence number (32)            | acknowledgement (32)       |
   +-------------------------------+-------------------------------+
   | advertised receive window (16) | payload length (16)          |
   +-------------------------------+-------------------------------+
   | CRC-32 of zeroed header + payload (32)                        |
   +---------------------------------------------------------------+

Sequence numbers count packets, beginning at zero.  ACK packets acknowledge an
individual packet number; the receiver advertises remaining buffer slots in the
window field.  DATA and FIN packets use the transfer id negotiated on TCP.
"""

from __future__ import annotations

import secrets
import struct
import zlib
from dataclasses import dataclass

MAGIC = b"HFTP"
VERSION = 1
HEADER_FORMAT = "!4sBBHQIIHHI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_PAYLOAD = 1_200
DEFAULT_WINDOW = 8

FLAG_DATA = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04
FLAG_FIN_ACK = 0x08
FLAG_ABORT = 0x10
KNOWN_FLAGS = FLAG_DATA | FLAG_ACK | FLAG_FIN | FLAG_FIN_ACK | FLAG_ABORT


class PacketError(ValueError):
    """Raised when a datagram does not meet the custom RDT contract."""


@dataclass(frozen=True)
class Packet:
    """One validated custom RDT packet."""

    flags: int
    transfer_id: int
    sequence: int = 0
    acknowledgement: int = 0
    window: int = DEFAULT_WINDOW
    payload: bytes = b""

    def encode(self) -> bytes:
        """Return a datagram with an integrity-protected fixed header."""

        _validate_packet(self)
        prefix = struct.pack(
            HEADER_FORMAT,
            MAGIC,
            VERSION,
            self.flags,
            HEADER_SIZE,
            self.transfer_id,
            self.sequence,
            self.acknowledgement,
            self.window,
            len(self.payload),
            0,
        )
        checksum = zlib.crc32(prefix + self.payload) & 0xFFFFFFFF
        header = prefix[:-4] + struct.pack("!I", checksum)
        return header + self.payload

    @classmethod
    def decode(cls, datagram: bytes) -> "Packet":
        """Decode and validate exactly one UDP datagram."""

        if len(datagram) < HEADER_SIZE:
            raise PacketError("datagram is shorter than the RDT header")
        fields = struct.unpack(HEADER_FORMAT, datagram[:HEADER_SIZE])
        magic, version, flags, header_size, transfer_id, sequence, acknowledgement, window, payload_length, checksum = fields
        if magic != MAGIC:
            raise PacketError("unknown RDT magic")
        if version != VERSION:
            raise PacketError("unsupported RDT version")
        if header_size != HEADER_SIZE:
            raise PacketError("invalid RDT header length")
        if flags == 0 or flags & ~KNOWN_FLAGS:
            raise PacketError("invalid RDT flags")
        if payload_length > MAX_PAYLOAD:
            raise PacketError("RDT payload exceeds maximum")
        if len(datagram) != HEADER_SIZE + payload_length:
            raise PacketError("RDT payload length does not match datagram")
        zeroed = datagram[: HEADER_SIZE - 4] + b"\x00\x00\x00\x00"
        if zlib.crc32(zeroed + datagram[HEADER_SIZE:]) & 0xFFFFFFFF != checksum:
            raise PacketError("RDT checksum mismatch")
        packet = cls(flags, transfer_id, sequence, acknowledgement, window, datagram[HEADER_SIZE:])
        _validate_packet(packet)
        return packet


def new_transfer_id() -> int:
    """Return a non-zero opaque identifier for one transfer."""

    return secrets.randbits(64) or 1


def data_packet(transfer_id: int, sequence: int, payload: bytes, window: int = DEFAULT_WINDOW) -> Packet:
    return Packet(FLAG_DATA, transfer_id, sequence=sequence, window=window, payload=payload)


def ack_packet(transfer_id: int, acknowledgement: int, window: int = DEFAULT_WINDOW) -> Packet:
    return Packet(FLAG_ACK, transfer_id, acknowledgement=acknowledgement, window=window)


def fin_packet(transfer_id: int, sequence: int) -> Packet:
    return Packet(FLAG_FIN, transfer_id, sequence=sequence)


def fin_ack_packet(transfer_id: int, acknowledgement: int) -> Packet:
    return Packet(FLAG_FIN_ACK, transfer_id, acknowledgement=acknowledgement)


def abort_packet(transfer_id: int) -> Packet:
    return Packet(FLAG_ABORT, transfer_id)


def _validate_packet(packet: Packet) -> None:
    if packet.flags == 0 or packet.flags & ~KNOWN_FLAGS:
        raise PacketError("invalid RDT flags")
    if packet.transfer_id <= 0 or packet.transfer_id > 0xFFFFFFFFFFFFFFFF:
        raise PacketError("invalid RDT transfer id")
    if not 0 <= packet.sequence <= 0xFFFFFFFF or not 0 <= packet.acknowledgement <= 0xFFFFFFFF:
        raise PacketError("sequence number outside uint32 range")
    if not 0 <= packet.window <= 0xFFFF:
        raise PacketError("window outside uint16 range")
    if len(packet.payload) > MAX_PAYLOAD:
        raise PacketError("RDT payload exceeds maximum")
    control_flags = packet.flags & (FLAG_ACK | FLAG_FIN | FLAG_FIN_ACK | FLAG_ABORT)
    if control_flags and packet.payload:
        raise PacketError("control packets must not carry payload")
    if packet.flags & FLAG_DATA and packet.flags != FLAG_DATA:
        raise PacketError("DATA cannot be combined with control flags")
