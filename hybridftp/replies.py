"""FTP-style reply helpers for the Hybrid FTP TCP control channel."""

from __future__ import annotations

from dataclasses import dataclass

CRLF = "\r\n"


@dataclass(frozen=True)
class Reply:
    """A three-digit FTP-style reply with one or more text lines."""

    code: int
    lines: tuple[str, ...]


def single(code: int, message: str) -> Reply:
    """Create a single-line reply."""

    return Reply(code=code, lines=(message,))


def multiline(code: int, lines: list[str], final: str) -> Reply:
    """Create an FTP multiline reply using a final terminating line."""

    return Reply(code=code, lines=tuple(lines) + (final,))


def format_reply(reply: Reply) -> bytes:
    """Encode a reply using UTF-8 and CRLF line endings."""

    if not reply.lines:
        text = f"{reply.code}"
        return f"{text}{CRLF}".encode("utf-8")
    if len(reply.lines) == 1:
        return f"{reply.code} {reply.lines[0]}{CRLF}".encode("utf-8")

    framed: list[str] = []
    for line in reply.lines[:-1]:
        framed.append(f"{reply.code}-{line}{CRLF}")
    framed.append(f"{reply.code} {reply.lines[-1]}{CRLF}")
    return "".join(framed).encode("utf-8")
