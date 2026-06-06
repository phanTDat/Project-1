"""Hybrid FTP Phase 1 TCP control server."""

from __future__ import annotations

import argparse
import logging
import queue
import socket
import threading
from dataclasses import dataclass
from pathlib import Path

from .commands import Command, MAX_CONTROL_LINE, ParseError, help_reply, is_protected_placeholder, parse_control_line
from .logging_utils import setup_logging
from .path_utils import resolve_server_root
from .replies import Reply, format_reply, single
from .session import DEMO_USERS, Session

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2121
DEFAULT_ROOT = Path("server_root")
GREETING = single(220, "Hybrid FTP server ready")
SYNTAX_ERROR = single(501, "Syntax error in parameters or arguments")


def sanitize_command_for_log(command: Command) -> str:
    """Return command text safe for logs, redacting PASS arguments."""

    if command.verb == "PASS":
        return "PASS ********"
    if command.argument:
        return f"{command.verb} {command.argument}"
    return command.verb


def _log(session: Session, logger: logging.Logger, message: str) -> None:
    logger.info(
        "session=%s client=%s:%s state=%s %s",
        session.session_id,
        session.client_address[0],
        session.client_address[1],
        session.state,
        message,
    )


def _handle_user(session: Session, command: Command, logger: logging.Logger) -> Reply:
    username = command.argument.strip()
    if not username:
        return single(501, "Syntax error in parameters or arguments")
    if username in DEMO_USERS:
        session.pending_username = username
        session.authenticated = False
        session.username = None
        session.state = "pending user"
        _log(session, logger, f"pending username={username}")
        return single(331, "User name okay, need password")
    session.pending_username = None
    _log(session, logger, f"invalid username={username}")
    return single(530, "Invalid username")


def _handle_pass(session: Session, command: Command, logger: logging.Logger) -> Reply:
    if session.pending_username is None:
        _log(session, logger, "PASS rejected: bad sequence")
        return single(503, "Bad sequence of commands")
    username = session.pending_username
    if DEMO_USERS.get(username) == command.argument:
        session.username = username
        session.pending_username = None
        session.authenticated = True
        session.state = "authenticated"
        _log(session, logger, f"authenticated username={username}")
        return single(230, "User logged in")
    session.pending_username = None
    session.authenticated = False
    session.username = None
    session.state = "connected"
    _log(session, logger, f"login failed username={username}")
    return single(530, "Login incorrect")


def _handle_noop(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return single(200, "NOOP ok")


def _handle_help(session: Session, command: Command, logger: logging.Logger) -> Reply:
    topic = command.argument.strip() or None
    return help_reply(topic)


def _handle_quit(session: Session, command: Command, logger: logging.Logger) -> Reply:
    session.state = "quit"
    _log(session, logger, "quit requested")
    return single(221, "Goodbye")


DISPATCH = {
    "USER": _handle_user,
    "PASS": _handle_pass,
    "NOOP": _handle_noop,
    "HELP": _handle_help,
    "QUIT": _handle_quit,
}


def handle_command(session: Session, command: Command, logger: logging.Logger) -> tuple[Reply, bool]:
    """Handle one parsed command and return reply plus close-session flag."""

    _log(session, logger, f"command={sanitize_command_for_log(command)}")
    if is_protected_placeholder(command.verb):
        if not session.authenticated:
            reply = single(530, "Not logged in")
            _log(session, logger, "protected placeholder blocked before login")
        else:
            reply = single(502, "Command not implemented yet")
            _log(session, logger, "protected placeholder deferred")
        _log(session, logger, f"reply={reply.code} {reply.lines[-1]}")
        return reply, False

    handler = DISPATCH.get(command.verb)
    if handler is None:
        reply = single(500, "Unknown command")
        _log(session, logger, f"reply={reply.code} {reply.lines[-1]}")
        return reply, False

    reply = handler(session, command, logger)
    close = command.verb == "QUIT"
    _log(session, logger, f"reply={reply.code} {reply.lines[-1]}")
    return reply, close


def _send_reply(conn: socket.socket, reply: Reply) -> None:
    conn.sendall(format_reply(reply))


def _read_control_line(conn: socket.socket, buffer: bytearray) -> bytes | None:
    while b"\n" not in buffer:
        try:
            chunk = conn.recv(1)
        except OSError:
            return None
        if not chunk:
            if buffer:
                raw = bytes(buffer)
                buffer.clear()
                return raw
            return None
        buffer.extend(chunk)
        if len(buffer) > MAX_CONTROL_LINE + 2:
            while chunk and chunk != b"\n":
                try:
                    chunk = conn.recv(1)
                except OSError:
                    break
            raw = bytes(buffer)
            buffer.clear()
            return raw
    index = buffer.index(10) + 1
    raw = bytes(buffer[:index])
    del buffer[:index]
    return raw


def _client_session(conn: socket.socket, address: tuple[str, int], session_id: int, root: Path, logger: logging.Logger) -> None:
    session = Session(session_id=session_id, client_address=address, server_root=root)
    _log(session, logger, "connect")
    with conn:
        _send_reply(conn, GREETING)
        _log(session, logger, f"reply={GREETING.code} {GREETING.lines[-1]}")
        buffer = bytearray()
        while True:
            raw = _read_control_line(conn, buffer)
            if raw is None:
                _log(session, logger, "disconnect without QUIT")
                break
            try:
                command = parse_control_line(raw)
            except ParseError as exc:
                logger.info(
                    "session=%s client=%s:%s state=%s malformed control line: %s",
                    session.session_id,
                    address[0],
                    address[1],
                    session.state,
                    exc,
                )
                _send_reply(conn, SYNTAX_ERROR)
                _log(session, logger, f"reply={SYNTAX_ERROR.code} {SYNTAX_ERROR.lines[-1]}")
                continue
            reply, close_session = handle_command(session, command, logger)
            _send_reply(conn, reply)
            if close_session:
                _log(session, logger, "disconnect after QUIT")
                break


def serve(
    host: str,
    port: int,
    root: Path,
    log_file: Path | None = None,
    ready_event: threading.Event | None = None,
    stop_event: threading.Event | None = None,
    bound_port_queue: queue.Queue[int] | None = None,
) -> int:
    """Run the single-client Phase 1 TCP control server."""

    logger = setup_logging(log_file=log_file)
    server_root = resolve_server_root(root)
    logger.info("server root=%s", server_root)
    stop_event = stop_event or threading.Event()
    session_counter = 0

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.listen(5)
            sock.settimeout(0.2)
            actual_port = sock.getsockname()[1]
            logger.info("listening host=%s port=%s", host, actual_port)
            if bound_port_queue is not None:
                bound_port_queue.put(actual_port)
            if ready_event is not None:
                ready_event.set()
            while not stop_event.is_set():
                try:
                    conn, address = sock.accept()
                except socket.timeout:
                    continue
                session_counter += 1
                _client_session(conn, address, session_counter, server_root, logger)
        logger.info("shutdown complete")
        return 0
    finally:
        for handler in list(logger.handlers):
            handler.flush()
            handler.close()
            logger.removeHandler(handler)


@dataclass
class TestServer:
    host: str
    port: int
    root: Path
    log_file: Path | None
    stop_event: threading.Event
    thread: threading.Thread

    def stop(self) -> None:
        self.stop_event.set()
        try:
            with socket.create_connection((self.host, self.port), timeout=0.5):
                pass
        except OSError:
            pass

    def join(self, timeout: float = 2.0) -> None:
        self.thread.join(timeout)


def start_test_server(root: Path, log_file: Path | None = None) -> TestServer:
    """Start the server on an ephemeral localhost port for tests and demos."""

    ready = threading.Event()
    stop = threading.Event()
    ports: queue.Queue[int] = queue.Queue(maxsize=1)
    thread = threading.Thread(
        target=serve,
        kwargs={
            "host": DEFAULT_HOST,
            "port": 0,
            "root": root,
            "log_file": log_file,
            "ready_event": ready,
            "stop_event": stop,
            "bound_port_queue": ports,
        },
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=2.0):
        raise RuntimeError("test server did not become ready")
    return TestServer(DEFAULT_HOST, ports.get(timeout=1.0), root, log_file, stop, thread)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid FTP TCP control server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--log-file", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        return serve(args.host, args.port, args.root, args.log_file)
    except KeyboardInterrupt:
        logger = logging.getLogger("hybridftp.server")
        if logger.handlers:
            logger.info("graceful shutdown requested by Ctrl+C")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
