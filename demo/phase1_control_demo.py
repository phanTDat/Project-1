"""Generate deterministic Phase 1 TCP control demo evidence."""

from __future__ import annotations

import io
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hybridftp.client import connect_and_run
from hybridftp.server import start_test_server

EVIDENCE_DIR = Path("demo/evidence/phase1")
TRANSCRIPT_PATH = EVIDENCE_DIR / "phase1-control-transcript.txt"
SERVER_LOG_PATH = EVIDENCE_DIR / "phase1-server.log"
DEMO_ROOT = EVIDENCE_DIR / "server_root_runtime"

COMMANDS = [
    "USER unknown",
    "PASS anything",
    "LIST",
    "USER student",
    "PASS wrong",
    "USER student",
    "PASS cs494",
    "HELP",
    "HELP USER",
    "NOOP",
    "BOGUS",
    "LIST",
    "QUIT",
]

EXPECTED_TRANSCRIPT = [
    "220 Hybrid FTP server ready",
    "530 Invalid username",
    "503 Bad sequence of commands",
    "530 Not logged in",
    "530 Login incorrect",
    "331 User name okay, need password",
    "230 User logged in",
    "214-",
    "200 NOOP ok",
    "500 Unknown command",
    "502 Command not implemented yet",
    "221 Goodbye",
    "ftp> PASS ********",
]


def _require_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"expected transcript/log to contain: {needle!r}")


def _require_absent(text: str, needle: str) -> None:
    if needle in text:
        raise AssertionError(f"sensitive raw value leaked into evidence: {needle!r}")


def _require_order(text: str, *needles: str) -> None:
    position = -1
    for needle in needles:
        next_position = text.find(needle, position + 1)
        if next_position == -1:
            raise AssertionError(f"missing {needle!r} after offset {position}")
        position = next_position


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT_PATH.write_text("", encoding="utf-8")
    SERVER_LOG_PATH.write_text("", encoding="utf-8")

    server = start_test_server(root=DEMO_ROOT, log_file=SERVER_LOG_PATH)
    transcript_buffer = io.StringIO()
    try:
        connect_and_run(server.host, server.port, commands=COMMANDS, transcript=transcript_buffer)
    finally:
        server.stop()
        server.join()

    transcript = transcript_buffer.getvalue()
    for expected in EXPECTED_TRANSCRIPT:
        _require_contains(transcript, expected)
    _require_order(
        transcript,
        "ftp> HELP\n",
        "214 End of help\n",
        "ftp> HELP USER\n",
        "214 End of help\n",
        "ftp> NOOP\n",
        "200 NOOP ok",
    )
    for secret in ("anything", "wrong", "cs494"):
        _require_absent(transcript, secret)

    transcript = transcript + "Phase 1 demo complete\n"
    TRANSCRIPT_PATH.write_text(transcript, encoding="utf-8")

    server_log = SERVER_LOG_PATH.read_text(encoding="utf-8")
    for expected in ("session=", "client=", "connect", "command=", "reply=", "authenticated", "quit", "disconnect"):
        _require_contains(server_log, expected)
    _require_contains(server_log, "PASS ********")
    for secret in ("anything", "wrong", "cs494"):
        _require_absent(server_log, secret)

    print("Phase 1 demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
