"""Interactive TCP-control / reliable-UDP Hybrid FTP client."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path
from typing import TextIO

from .data_channel import parse_passive_reply
from .integrity import HashComparison, sha256_path
from .replies import CRLF
from .transfer import TransferError, receive_file, send_file, sha256_ascii_path

PROMPT = "ftp> "
LOCAL_NOT_CONNECTED = "530 Not connected; use open <host> <port>"
LOCAL_SYNTAX = "501 Syntax error in parameters or arguments"


def _write(line: str, transcript: TextIO | None) -> None:
    print(line)
    if transcript is not None:
        transcript.write(line + "\n")
        transcript.flush()


def _redacted_echo(command: str) -> str:
    parts = command.strip().split(maxsplit=1)
    return "PASS ********" if parts and parts[0].upper() == "PASS" else command.strip()


def _read_line(sock: socket.socket) -> str:
    data = bytearray()
    while not data.endswith(b"\n"):
        chunk = sock.recv(1)
        if not chunk:
            break
        data.extend(chunk)
    return data.decode("utf-8", errors="replace").rstrip("\r\n")


def _read_reply(sock: socket.socket, transcript: TextIO | None) -> list[str]:
    first = _read_line(sock)
    if not first:
        return []
    lines = [first]
    _write(first, transcript)
    if len(first) >= 4 and first[:3].isdigit() and first[3] == "-":
        terminator = first[:3] + " "
        while True:
            line = _read_line(sock)
            if not line:
                break
            lines.append(line)
            _write(line, transcript)
            if line.startswith(terminator):
                break
    return lines


def _send_raw(sock: socket.socket, command: str, transcript: TextIO | None) -> None:
    _write(PROMPT + _redacted_echo(command), transcript)
    sock.sendall((command.rstrip("\r\n") + CRLF).encode("utf-8"))


def _send_command(sock: socket.socket, command: str, transcript: TextIO | None) -> list[str]:
    _send_raw(sock, command, transcript)
    return _read_reply(sock, transcript)


def _reply_code(reply: list[str]) -> int | None:
    try:
        return int(reply[0][:3]) if reply else None
    except ValueError:
        return None


def _transfer_id(reply: list[str]) -> int:
    for line in reply:
        marker = "transfer_id="
        if marker in line:
            return int(line.split(marker, 1)[1].split()[0])
    raise TransferError("server did not provide transfer_id in 150 reply")


def _passive_endpoint(sock: socket.socket, transcript: TextIO | None):
    reply = _send_command(sock, "PASV", transcript)
    if _reply_code(reply) != 227:
        raise TransferError("PASV was rejected")
    return parse_passive_reply(reply[-1])


def _display_hash_check(sock: socket.socket, remote: str, local: Path, transcript: TextIO | None, *, ascii_mode: bool) -> None:
    reply = _send_command(sock, f"HASH {remote}", transcript)
    if _reply_code(reply) != 213:
        return
    local_hash = sha256_ascii_path(local) if ascii_mode else sha256_path(local)
    comparison = HashComparison(local_hash, reply[-1][4:].strip())
    _write(f"SHA-256 local={comparison.local} server={comparison.remote} match={comparison.matches}", transcript)


def _put(sock: socket.socket, local: Path, remote: str, command: str, transcript: TextIO | None, *, ascii_mode: bool) -> None:
    if not local.is_file():
        _write("550 Local source is not a regular file", transcript)
        return
    try:
        if ascii_mode:
            sha256_ascii_path(local)
        endpoint = _passive_endpoint(sock, transcript)
        _send_raw(sock, f"{command} {remote}".rstrip(), transcript)
        preliminary = _read_reply(sock, transcript)
        if _reply_code(preliminary) != 150:
            return
        transfer_id = _transfer_id(preliminary)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            result = send_file(udp, (endpoint.host, endpoint.port), local, transfer_id, ascii_mode=ascii_mode)
        _write(f"UDP upload bytes={result.bytes_transferred} sha256={result.sha256}", transcript)
        final = _read_reply(sock, transcript)
        if _reply_code(final) == 226:
            _display_hash_check(sock, remote, local, transcript, ascii_mode=ascii_mode)
    except (OSError, TransferError, ValueError) as exc:
        _write(f"426 Local transfer failed: {exc}", transcript)


def _get(sock: socket.socket, remote: str, local: Path, transcript: TextIO | None, *, ascii_mode: bool) -> None:
    try:
        endpoint = _passive_endpoint(sock, transcript)
        _send_raw(sock, f"RETR {remote}", transcript)
        preliminary = _read_reply(sock, transcript)
        if _reply_code(preliminary) != 150:
            return
        transfer_id = _transfer_id(preliminary)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
            udp.bind(("127.0.0.1", 0))
            result = receive_file(udp, (endpoint.host, endpoint.port), local, transfer_id, send_ready=True, ascii_mode=ascii_mode)
        _write(f"UDP download bytes={result.bytes_transferred} sha256={result.sha256}", transcript)
        final = _read_reply(sock, transcript)
        if _reply_code(final) == 226:
            _display_hash_check(sock, remote, local, transcript, ascii_mode=ascii_mode)
    except (OSError, TransferError, ValueError) as exc:
        _write(f"426 Local transfer failed: {exc}", transcript)


def _local_transfer(sock: socket.socket, command: str, transcript: TextIO | None, *, ascii_mode: bool) -> bool:
    """Run human-friendly local aliases; return whether ``command`` was handled."""

    parts = command.split()
    if not parts:
        return True
    verb = parts[0].lower()
    if verb == "put" and len(parts) in {2, 3}:
        local = Path(parts[1])
        _put(sock, local, parts[2] if len(parts) == 3 else local.name, "STOR", transcript, ascii_mode=ascii_mode)
        return True
    if verb == "append" and len(parts) == 3:
        _put(sock, Path(parts[1]), parts[2], "APPE", transcript, ascii_mode=ascii_mode)
        return True
    if verb == "put-unique" and len(parts) in {2, 3}:
        local = Path(parts[1])
        _put(sock, local, parts[2] if len(parts) == 3 else local.name, "STOU", transcript, ascii_mode=ascii_mode)
        return True
    if verb == "get" and len(parts) in {2, 3}:
        remote = parts[1]
        local = Path(parts[2]) if len(parts) == 3 else Path(Path(remote).name)
        _get(sock, remote, local, transcript, ascii_mode=ascii_mode)
        return True
    return False


def _run_connected(sock: socket.socket, commands: list[str] | None, transcript: TextIO | None) -> None:
    _read_reply(sock, transcript)
    transfer_type = "I"
    iterator = iter(commands or [])
    while True:
        try:
            command = next(iterator) if commands is not None else input(PROMPT)
        except (EOFError, StopIteration):
            break
        if not command:
            continue
        if _local_transfer(sock, command, transcript, ascii_mode=transfer_type == "A"):
            continue
        replies = _send_command(sock, command, transcript)
        if command.strip().upper() in {"TYPE A", "TYPE I"} and _reply_code(replies) == 200:
            transfer_type = command.strip().upper()[-1]
        if command.strip().upper() == "QUIT" or not replies:
            break


def connect_and_run(host: str, port: int, commands: list[str] | None = None, transcript: TextIO | None = None) -> int:
    with socket.create_connection((host, port), timeout=5.0) as sock:
        _run_connected(sock, commands, transcript)
    return 0


def _parse_open(command: str, default_host: str, default_port: int) -> tuple[str, int] | None:
    parts = command.split()
    if not parts or parts[0].lower() != "open" or len(parts) > 3:
        return None
    try:
        return parts[1] if len(parts) >= 2 else default_host, int(parts[2]) if len(parts) == 3 else default_port
    except ValueError:
        return None


def open_style_run(default_host: str = "127.0.0.1", default_port: int = 2121, commands: list[str] | None = None, transcript: TextIO | None = None) -> int:
    sock: socket.socket | None = None
    transfer_type = "I"
    iterator = iter(commands or [])
    try:
        while True:
            try:
                command = next(iterator) if commands is not None else input(PROMPT)
            except (EOFError, StopIteration):
                break
            if not command:
                continue
            if sock is None:
                _write(PROMPT + _redacted_echo(command), transcript)
                parsed = _parse_open(command, default_host, default_port) if command.strip().lower().startswith("open") else None
                if parsed is None:
                    _write(LOCAL_SYNTAX if command.strip().lower().startswith("open") else LOCAL_NOT_CONNECTED, transcript)
                    continue
                sock = socket.create_connection(parsed, timeout=5.0)
                _read_reply(sock, transcript)
                continue
            if _local_transfer(sock, command, transcript, ascii_mode=transfer_type == "A"):
                continue
            replies = _send_command(sock, command, transcript)
            if command.strip().upper() in {"TYPE A", "TYPE I"} and _reply_code(replies) == 200:
                transfer_type = command.strip().upper()[-1]
            if command.strip().upper() == "QUIT" or not replies:
                break
    finally:
        if sock is not None:
            sock.close()
    return 0


def _commands_from_arg(value: str | None) -> list[str] | None:
    return [part.strip() for part in value.split(";") if part.strip()] if value is not None else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid FTP TCP-control / reliable-UDP client")
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=2121)
    parser.add_argument("--commands", help="semicolon-separated commands; use put/get aliases for local files")
    parser.add_argument("--no-connect", action="store_true", help="start disconnected and use open <host> <port>")
    args = parser.parse_args(argv)
    commands = _commands_from_arg(args.commands)
    return open_style_run(args.host, args.port, commands, None) if args.no_connect else connect_and_run(args.host, args.port, commands, None)


if __name__ == "__main__":
    raise SystemExit(main())
