"""Generate curated Excellent-level Hybrid FTP final demo evidence."""

from __future__ import annotations

import io
import re
import socket
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hybridftp.client import connect_and_run
from hybridftp.integrity import sha256_path
from hybridftp.server import start_test_server

EVIDENCE_DIR = PROJECT_ROOT / "demo" / "evidence" / "final"
TRANSCRIPT = EVIDENCE_DIR / "final-transfer-transcript.txt"
SERVER_LOG = EVIDENCE_DIR / "final-server.log"


def redact(text: str, root: Path) -> str:
    text = text.replace("PASS ********", "PASS <redacted>").replace(str(root.resolve()), "<server_root>").replace("cs494", "<redacted-password>")
    text = re.sub(r"transfer_id=\d+", "transfer_id=<id>", text)
    text = re.sub(r"transfer=id=\d+", "transfer=id=<id>", text)
    text = re.sub(r"\brdt (send|receive|ack|window|fin|ready|passive peer ready|window drain|window advance) id=\d+", r"rdt \1 id=<id>", text)
    text = re.sub(r"transfer (prepared|complete) id=\d+", r"transfer \1 id=<id>", text)
    text = re.sub(r"client=127\.0\.0\.1:\d+", "client=127.0.0.1:<port>", text)
    text = re.sub(r"session=\d+ client=", "session=<id> client=", text)
    return text


def _reply(sock: socket.socket) -> str:
    data = bytearray()
    while not data.endswith(b"\r\n"):
        chunk = sock.recv(1)
        if not chunk:
            raise AssertionError("control connection closed before reply")
        data.extend(chunk)
    return data.decode("utf-8").rstrip("\r\n")


def _send(sock: socket.socket, command: str) -> str:
    sock.sendall((command + "\r\n").encode("utf-8"))
    return _reply(sock)


def _multiline_reply(sock: socket.socket) -> list[str]:
    first = _reply(sock)
    lines = [first]
    if len(first) >= 4 and first[3] == "-":
        terminator = first[:3] + " "
        while not lines[-1].startswith(terminator):
            lines.append(_reply(sock))
    return lines


def _concurrency_evidence(server, root: Path) -> str:
    (root / "client-one").mkdir()
    (root / "client-two").mkdir()
    first = socket.create_connection((server.host, server.port), timeout=2)
    second = socket.create_connection((server.host, server.port), timeout=2)
    try:
        for client in (first, second):
            if not _reply(client).startswith("220"):
                raise AssertionError("missing greeting")
            if not _send(client, "USER student").startswith("331"):
                raise AssertionError("USER failed")
            if not _send(client, "PASS cs494").startswith("230"):
                raise AssertionError("PASS failed")
        if not _send(first, "CWD client-one").startswith("250"):
            raise AssertionError("first CWD failed")
        if not _send(second, "CWD client-two").startswith("250"):
            raise AssertionError("second CWD failed")
        first.sendall(b"STAT\r\n")
        status = _multiline_reply(first)
        if not any("active_sessions=2" in line for line in status):
            raise AssertionError("missing two-client session table")
        if not any("cwd=/client-one" in line for line in status) or not any("cwd=/client-two" in line for line in status):
            raise AssertionError("working directories are not isolated")
        _send(first, "QUIT")
        _send(second, "QUIT")
        return "\n".join(["CONCURRENT SESSION CHECK", *status])
    finally:
        first.close()
        second.close()


def main() -> int:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPT.write_text("", encoding="utf-8")
    SERVER_LOG.write_text("", encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="hybridftp-final-") as tmp:
        root = Path(tmp) / "server"
        local = Path(tmp) / "binary-fixture.bin"
        downloaded = Path(tmp) / "downloaded.bin"
        local.write_bytes(bytes(range(256)) * 16 + b"Hybrid FTP final binary fixture\x00")
        server = start_test_server(root, SERVER_LOG)
        transcript = io.StringIO()
        try:
            connect_and_run(
                server.host,
                server.port,
                commands=[
                    "USER student",
                    "PASS cs494",
                    "TYPE I",
                    "MODE S",
                    f"put {local} evidence.bin",
                    f"get evidence.bin {downloaded}",
                    "STAT",
                    "QUIT",
                ],
                transcript=transcript,
            )
            concurrency = _concurrency_evidence(server, root)
        finally:
            server.stop()
            server.join()
        if sha256_path(local) != sha256_path(downloaded):
            raise AssertionError("binary evidence hash mismatch")
        text = redact(transcript.getvalue(), root) + "\n" + redact(concurrency, root) + "\n"
        log = redact(SERVER_LOG.read_text(encoding="utf-8"), root)
    for required in ["150 Opening UDP data connection", "226 Transfer complete", "SHA-256 local=", "match=True", "active_sessions=1", "CONCURRENT SESSION CHECK", "active_sessions=2", "cwd=/client-one", "cwd=/client-two", "221 Goodbye"]:
        if required not in text:
            raise AssertionError(f"missing final evidence: {required}")
    for required in ["rdt send", "rdt ack", "rdt window", "transfer complete"]:
        if required not in log:
            raise AssertionError(f"missing server log evidence: {required}")
    TRANSCRIPT.write_text(text + "Final submission demo complete\n", encoding="utf-8")
    SERVER_LOG.write_text(log, encoding="utf-8")
    print("Final submission demo complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
