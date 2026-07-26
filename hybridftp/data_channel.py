"""FTP-style UDP endpoint helpers for active and passive Hybrid FTP modes."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass


class DataChannelError(ValueError):
    """Raised for invalid or unsafe UDP endpoint negotiation."""


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int


def parse_port_argument(argument: str, *, control_peer_host: str | None = None) -> Endpoint:
    """Parse an RFC-style ``h1,h2,h3,h4,p1,p2`` active-mode endpoint.

    The endpoint must be a unicast IPv4 address and a non-zero port.  When a
    control peer is supplied, require the UDP peer to be that same address so a
    client cannot direct the server at an unrelated host.
    """

    parts = [part.strip() for part in argument.split(",")]
    if len(parts) != 6:
        raise DataChannelError("PORT requires h1,h2,h3,h4,p1,p2")
    try:
        values = [int(part) for part in parts]
    except ValueError as exc:
        raise DataChannelError("PORT values must be decimal integers") from exc
    if any(value < 0 or value > 255 for value in values):
        raise DataChannelError("PORT values must be between 0 and 255")
    host = ".".join(str(value) for value in values[:4])
    address = ipaddress.ip_address(host)
    if not address.is_private and not address.is_loopback:
        raise DataChannelError("PORT host must be a local or private address")
    if address.is_multicast or address.is_unspecified:
        raise DataChannelError("PORT host must be a unicast address")
    if control_peer_host is not None and host != control_peer_host:
        raise DataChannelError("PORT host must match the TCP control client")
    port = values[4] * 256 + values[5]
    if port == 0:
        raise DataChannelError("PORT must specify a non-zero UDP port")
    return Endpoint(host, port)


def format_passive_reply(endpoint: Endpoint) -> str:
    """Format a UDP passive endpoint in the conventional FTP tuple form."""

    try:
        octets = [int(part) for part in endpoint.host.split(".")]
    except ValueError as exc:
        raise DataChannelError("PASV requires an IPv4 endpoint") from exc
    if len(octets) != 4 or any(part < 0 or part > 255 for part in octets):
        raise DataChannelError("PASV requires an IPv4 endpoint")
    if not 1 <= endpoint.port <= 65535:
        raise DataChannelError("PASV port is outside range")
    high, low = divmod(endpoint.port, 256)
    return "(" + ",".join(str(part) for part in (*octets, high, low)) + ")"


def parse_passive_reply(text: str) -> Endpoint:
    """Parse the host/port tuple returned in a 227 passive-mode reply."""

    start, end = text.find("("), text.find(")")
    if start < 0 or end <= start:
        raise DataChannelError("PASV reply does not contain an endpoint tuple")
    return parse_port_argument(text[start + 1 : end])


def bind_passive_socket(host: str) -> tuple[socket.socket, Endpoint]:
    """Bind one UDP passive socket and return it with its advertised endpoint."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, 0))
    bound_host, port = sock.getsockname()[:2]
    return sock, Endpoint(bound_host, port)
