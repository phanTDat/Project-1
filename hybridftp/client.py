"""Hybrid FTP Phase 1 TCP control client."""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path
from typing import TextIO

from .replies import CRLF

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
    if parts and parts[0].upper() == "PASS":
        return "PASS ********"
    return command.strip()


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


def _send_command(sock: socket.socket, command: str, transcript: TextIO | None) -> list[str]:
    _write(PROMPT + _redacted_echo(command), transcript)
    sock.sendall((command.rstrip("\r\n") + CRLF).encode("utf-8"))
    return _read_reply(sock, transcript)


def connect_and_run(host: str, port: int, commands: list[str] | None = None, transcript: TextIO | None = None) -> int:
    """Connect immediately, print raw replies, and optionally run scripted commands."""

    with socket.create_connection((host, port), timeout=5.0) as sock:
        _read_reply(sock, transcript)
        if commands is None:
            while True:
                try:
                    command = input(PROMPT)
                except EOFError:
                    break
                if not command:
                    continue
                replies = _send_command(sock, command, transcript)
                if command.strip().upper() == "QUIT" or not replies:
                    break
        else:
            for command in commands:
                replies = _send_command(sock, command, transcript)
                if command.strip().upper() == "QUIT" or not replies:
                    break
    return 0


def _parse_open(command: str, default_host: str, default_port: int) -> tuple[str, int] | None:
    parts = command.split()
    if not parts or parts[0].lower() != "open" or len(parts) > 3:
        return None
    host = parts[1] if len(parts) >= 2 else default_host
    if len(parts) == 3:
        try:
            port = int(parts[2])
        except ValueError:
            return None
    else:
        port = default_port
    return host, port


def open_style_run(
    default_host: str = "127.0.0.1",
    default_port: int = 2121,
    commands: list[str] | None = None,
    transcript: TextIO | None = None,
) -> int:
    """Run an FTP-like disconnected shell with local open support."""

    sock: socket.socket | None = None
    scripted = commands is not None
    iterator = iter(commands or [])
    try:
        while True:
            if scripted:
                try:
                    command = next(iterator)
                except StopIteration:
                    break
            else:
                try:
                    command = input(PROMPT)
                except EOFError:
                    break
            if not command:
                continue
            if sock is None:
                _write(PROMPT + _redacted_echo(command), transcript)
                if command.strip().lower().startswith("open"):
                    parsed = _parse_open(command, default_host, default_port)
                    if parsed is None:
                        _write(LOCAL_SYNTAX, transcript)
                        continue
                    host, port = parsed
                    sock = socket.create_connection((host, port), timeout=5.0)
                    _read_reply(sock, transcript)
                else:
                    _write(LOCAL_NOT_CONNECTED, transcript)
                continue
            replies = _send_command(sock, command, transcript)
            if command.strip().upper() == "QUIT" or not replies:
                break
    finally:
        if sock is not None:
            sock.close()
    return 0


def _commands_from_arg(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [part.strip() for part in value.split(";") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid FTP TCP control client")
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=2121)
    parser.add_argument("--commands", help="semicolon-separated command list for scripted runs")
    parser.add_argument("--no-connect", action="store_true", help="start disconnected and use open <host> <port>")
    args = parser.parse_args(argv)
    commands = _commands_from_arg(args.commands)
    if args.no_connect:
        return open_style_run(args.host, args.port, commands=commands)
    return connect_and_run(args.host, args.port, commands=commands)


if __name__ == "__main__":
    raise SystemExit(main())
