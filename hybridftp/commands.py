"""Command parsing and HELP catalog for the Hybrid FTP control channel."""

from __future__ import annotations

from dataclasses import dataclass

from .replies import Reply, multiline

MAX_CONTROL_LINE = 1024

PHASE1_COMMANDS = {"USER", "PASS", "HELP", "NOOP", "QUIT"}
FILESYSTEM_COMMANDS = {"PWD", "CWD", "CDUP", "MKD", "RMD", "LIST", "NLST", "STAT", "SIZE", "MDTM", "DELE", "RNFR", "RNTO"}
DATA_COMMANDS = {"TYPE", "MODE", "PASV", "PORT", "RETR", "STOR", "STOU", "APPE", "ABOR", "HASH"}

HELP_TOPICS: dict[str, str] = {
    "USER": "USER <username> - begin login with the demo account username.",
    "PASS": "PASS <password> - complete login after USER; password text is never logged.",
    "HELP": "HELP [command] - show this catalog or command-specific help.",
    "NOOP": "NOOP - keep the TCP control connection alive.",
    "QUIT": "QUIT - close the TCP control session gracefully.",
    "PWD": "PWD - print the session's virtual server working directory.",
    "CWD": "CWD <path> - change the session directory inside the server root.",
    "CDUP": "CDUP - move to the parent directory without leaving the server root.",
    "MKD": "MKD <path> - create a new directory inside the server root.",
    "RMD": "RMD <path> - remove an existing empty directory inside the server root.",
    "LIST": "LIST [path] - show a detailed TCP control-channel listing.",
    "NLST": "NLST [path] - show a name-only TCP control-channel listing.",
    "STAT": "STAT [path] - show session status or file/directory metadata.",
    "SIZE": "SIZE <path> - return byte size for a regular file.",
    "MDTM": "MDTM <path> - return UTC modification time as YYYYMMDDhhmmss.",
    "DELE": "DELE <path> - delete an existing regular file inside the server root.",
    "RNFR": "RNFR <path> - choose an existing file or directory as a rename source.",
    "RNTO": "RNTO <path> - rename the pending RNFR source to a safe destination.",
    "TYPE": "TYPE {A|I} - select ASCII or binary transfer type; payload bytes remain UDP data.",
    "MODE": "MODE {S|B|C} - S is supported; B and C return a clear unsupported reply.",
    "PASV": "PASV - open a per-session UDP endpoint and return it in a 227 reply.",
    "PORT": "PORT h1,h2,h3,h4,p1,p2 - set the client's active UDP endpoint.",
    "RETR": "RETR <path> - download a server file through reliable UDP.",
    "STOR": "STOR <path> - upload bytes through reliable UDP.",
    "STOU": "STOU - upload to a unique server-generated filename through reliable UDP.",
    "APPE": "APPE <path> - append a verified UDP upload to a server file.",
    "ABOR": "ABOR - cancel the active UDP transfer and clean temporary data.",
    "HASH": "HASH <path> - return the server file SHA-256 digest.",
}


class ParseError(ValueError):
    """Raised when a TCP control line is malformed."""


@dataclass(frozen=True)
class Command:
    """Parsed command verb and argument text."""

    verb: str
    argument: str = ""


def parse_control_line(raw: bytes) -> Command:
    """Parse one UTF-8 FTP control line."""

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
    return Command(parts[0].upper(), parts[1] if len(parts) == 2 else "")


def is_protected_placeholder(verb: str) -> bool:
    """Compatibility predicate retained for earlier callers and tests."""

    return verb.upper() in DATA_COMMANDS


def is_filesystem_command(verb: str) -> bool:
    return verb.upper() in FILESYSTEM_COMMANDS


def is_data_command(verb: str) -> bool:
    return verb.upper() in DATA_COMMANDS


def help_reply(topic: str | None = None) -> Reply:
    normalized = topic.upper() if topic else None
    if normalized:
        if normalized in HELP_TOPICS:
            return multiline(214, [HELP_TOPICS[normalized]], "End of help")
        return multiline(214, [f"No help available for {normalized}."], "End of help")
    lines = [
        "Control commands:",
        "  " + " ".join(sorted(PHASE1_COMMANDS)),
        "Filesystem commands:",
        "  " + " ".join(sorted(FILESYSTEM_COMMANDS)),
        "UDP data commands:",
        "  " + " ".join(sorted(DATA_COMMANDS)),
    ]
    return multiline(214, lines, "End of help")
