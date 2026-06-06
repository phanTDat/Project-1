"""Command parsing and HELP catalog for the Hybrid FTP control channel."""

from __future__ import annotations

from dataclasses import dataclass

from .replies import Reply, multiline

MAX_CONTROL_LINE = 1024

PHASE1_COMMANDS = {"USER", "PASS", "HELP", "NOOP", "QUIT"}

PROTECTED_PLACEHOLDERS = {
    "PWD",
    "CWD",
    "CDUP",
    "MKD",
    "RMD",
    "LIST",
    "NLST",
    "STAT",
    "SIZE",
    "MDTM",
    "DELE",
    "RNFR",
    "RNTO",
    "TYPE",
    "MODE",
    "PASV",
    "PORT",
    "RETR",
    "STOR",
    "STOU",
    "APPE",
    "ABOR",
    "HASH",
}

HELP_TOPICS: dict[str, str] = {
    "USER": "USER <username> - begin login with the demo account username.",
    "PASS": "PASS <password> - complete login after USER; password text is never logged.",
    "HELP": "HELP [command] - show this catalog or command-specific help.",
    "NOOP": "NOOP - keep the TCP control connection alive.",
    "QUIT": "QUIT - close the TCP control session gracefully.",
}


class ParseError(ValueError):
    """Raised when a TCP control line is malformed."""


@dataclass(frozen=True)
class Command:
    """Parsed command verb and argument text."""

    verb: str
    argument: str = ""


def parse_control_line(raw: bytes) -> Command:
    """Parse one UTF-8 FTP control line.

    CRLF and LF are accepted. The command verb is uppercased while the
    argument text after the first whitespace is preserved exactly.
    """

    if len(raw) > MAX_CONTROL_LINE + 2:
        raise ParseError("control line too long")
    if not (raw.endswith(b"\n") or raw.endswith(b"\r\n")):
        raise ParseError("control line missing terminator")
    line_bytes = raw.rstrip(b"\r\n")
    if len(line_bytes) > MAX_CONTROL_LINE:
        raise ParseError("control line too long")
    try:
        line = line_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("control line is not valid UTF-8") from exc
    if not line.strip():
        raise ParseError("empty command")

    parts = line.split(maxsplit=1)
    verb = parts[0].upper()
    argument = parts[1] if len(parts) == 2 else ""
    return Command(verb=verb, argument=argument)


def is_protected_placeholder(verb: str) -> bool:
    """Return whether a command is a recognized future protected command."""

    return verb.upper() in PROTECTED_PLACEHOLDERS


def help_reply(topic: str | None = None) -> Reply:
    """Return a server-side FTP HELP reply."""

    normalized = topic.upper() if topic else None
    if normalized:
        if normalized in HELP_TOPICS:
            return multiline(214, [HELP_TOPICS[normalized]], "End of help")
        if normalized in PROTECTED_PLACEHOLDERS:
            return multiline(
                214,
                [f"{normalized} - coming soon in a later Hybrid FTP phase."],
                "End of help",
            )
        return multiline(214, [f"No help available for {normalized}."], "End of help")

    lines = [
        "Phase 1 commands:",
        "  USER <username>",
        "  PASS <password>",
        "  HELP [command]",
        "  NOOP",
        "  QUIT",
        "Future protected commands (coming soon):",
        "  " + " ".join(sorted(PROTECTED_PLACEHOLDERS)),
    ]
    return multiline(214, lines, "End of help")
