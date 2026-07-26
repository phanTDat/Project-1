"""Hybrid FTP TCP control server with custom reliable UDP data transfers."""

from __future__ import annotations

import argparse
import logging
import queue
import socket
import threading
from dataclasses import dataclass
from pathlib import Path

from .commands import Command, MAX_CONTROL_LINE, ParseError, help_reply, is_data_command, is_filesystem_command, parse_control_line
from .data_channel import DataChannelError, bind_passive_socket, format_passive_reply, parse_port_argument
from .filesystem import (
    FilesystemError,
    change_directory,
    change_to_parent,
    delete_file,
    file_size,
    list_detailed,
    list_names,
    make_directory,
    modified_time,
    remove_directory,
    rename_from,
    rename_to,
    resolve_virtual_path,
    stat_path,
    virtual_to_text,
)
from .integrity import sha256_path
from .logging_utils import setup_logging
from .path_utils import resolve_server_root
from .rdt import new_transfer_id
from .replies import Reply, format_reply, multiline, single
from .session import DEMO_USERS, Session, TransferRequest
from .session_registry import SessionRegistry
from .transfer import TransferAborted, TransferError, receive_file, send_file

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2121
DEFAULT_ROOT = Path("server_root")
GREETING = single(220, "Hybrid FTP server ready")
SYNTAX_ERROR = single(501, "Syntax error in parameters or arguments")


class ServerContext:
    """Shared, lock-protected server services used by session workers."""

    def __init__(self) -> None:
        self.registry = SessionRegistry()
        self.counter = 0
        self.counter_lock = threading.Lock()
        self.workers: set[threading.Thread] = set()
        self.workers_lock = threading.Lock()
        self.file_locks: dict[Path, threading.Lock] = {}
        self.file_locks_lock = threading.Lock()

    def next_session_id(self) -> int:
        with self.counter_lock:
            self.counter += 1
            return self.counter

    def file_lock(self, path: Path) -> threading.Lock:
        with self.file_locks_lock:
            return self.file_locks.setdefault(path.resolve(), threading.Lock())


def sanitize_command_for_log(command: Command) -> str:
    if command.verb == "PASS":
        return "PASS ********"
    return f"{command.verb} {command.argument}" if command.argument else command.verb


def _log(session: Session, logger: logging.Logger, message: str) -> None:
    logger.info("session=%s client=%s:%s state=%s %s", session.session_id, session.client_address[0], session.client_address[1], session.state, message)


def _safe_reply(exc: FilesystemError) -> Reply:
    if exc.code == 501:
        return SYNTAX_ERROR
    if exc.code == 503:
        return single(503, exc.message)
    return single(550, exc.message)


def _require_argument(command: Command) -> str:
    argument = command.argument.strip()
    if not argument:
        raise FilesystemError("Syntax error in parameters or arguments", 501)
    return argument


def _transfer_is_active(session: Session) -> bool:
    return session.transfer.direction != "idle"


def _cancel_transfer(session: Session) -> threading.Thread | None:
    with session.transfer.lock:
        if not _transfer_is_active(session):
            return None
        session.transfer.cancel.set()
        return session.transfer.worker


def _reset_data_state(session: Session) -> None:
    with session.transfer.lock:
        session.transfer.close_socket()
        session.transfer.direction = "idle"
        session.transfer.transfer_id = None
        session.transfer.worker = None
        session.pending_transfer = None
        session.data_mode = "NONE"
        session.active_endpoint = None
        session.passive_endpoint = None


def _cancel_and_join_transfer(session: Session) -> None:
    worker = _cancel_transfer(session)
    if worker is not None and worker is not threading.current_thread():
        worker.join(timeout=2.0)
    if worker is None or not worker.is_alive():
        _reset_data_state(session)


def _handle_user(session: Session, command: Command, logger: logging.Logger) -> Reply:
    username = command.argument.strip()
    if not username:
        return SYNTAX_ERROR
    if username in DEMO_USERS:
        session.pending_username, session.authenticated, session.username, session.state = username, False, None, "pending user"
        return single(331, "User name okay, need password")
    session.pending_username = None
    return single(530, "Invalid username")


def _handle_pass(session: Session, command: Command, logger: logging.Logger) -> Reply:
    if session.pending_username is None:
        return single(503, "Bad sequence of commands")
    username = session.pending_username
    session.pending_username = None
    if DEMO_USERS.get(username) == command.argument:
        session.username, session.authenticated, session.state = username, True, "authenticated"
        _log(session, logger, f"authenticated username={username}")
        return single(230, "User logged in")
    session.username, session.authenticated, session.state = None, False, "connected"
    return single(530, "Login incorrect")


def _handle_noop(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return single(200, "NOOP ok")


def _handle_help(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return help_reply(command.argument.strip() or None)


def _handle_quit(session: Session, command: Command, logger: logging.Logger) -> Reply:
    _cancel_transfer(session)
    session.rename_from_real = session.rename_from_virtual = None
    session.state = "quit"
    return single(221, "Goodbye")


def _handle_pwd(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return single(257, f'"{virtual_to_text(session.cwd)}" is current directory')


def _handle_cwd(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        target = change_directory(session, command.argument)
        return single(250, f'Directory changed to "{virtual_to_text(target)}"')
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_cdup(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        target = change_to_parent(session)
        return single(250, f'Directory changed to "{virtual_to_text(target)}"')
    except FilesystemError as exc:
        return _safe_reply(exc)


def _listing_reply(session: Session, command: Command, names_only: bool) -> Reply:
    try:
        _, lines = list_names(session, command.argument) if names_only else list_detailed(session, command.argument)
        return multiline(212, lines or ["(empty)"], "End")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_list(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return _listing_reply(session, command, False)


def _handle_nlst(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return _listing_reply(session, command, True)


def _session_status_lines(session: Session, context: ServerContext) -> list[str]:
    pending = virtual_to_text(session.rename_from_virtual) if session.rename_from_virtual else "none"
    endpoint = session.passive_endpoint or session.active_endpoint
    endpoint_text = f"{endpoint.host}:{endpoint.port}" if endpoint else "none"
    return [
        f"user={session.username or '-'} state={session.state}",
        f"cwd={virtual_to_text(session.cwd)} root=/",
        "implemented=PWD CWD CDUP LIST NLST STAT SIZE MDTM MKD RMD DELE RNFR RNTO TYPE MODE PASV PORT RETR STOR STOU APPE ABOR HASH",
        f"type={session.transfer_type} mode={session.transfer_mode} data_mode={session.data_mode} endpoint={endpoint_text}",
        f"transfer=id={session.transfer.transfer_id or 'none'} direction={session.transfer.direction} bytes={session.transfer.bytes_transferred}",
        f"pending_rename={pending}",
        *context.registry.status_lines(),
    ]


def _handle_stat(session: Session, command: Command, logger: logging.Logger, context: ServerContext) -> Reply:
    try:
        if not command.argument.strip():
            return multiline(212, _session_status_lines(session, context), "End")
        _, line = stat_path(session, command.argument)
        return multiline(212, [line], "End")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_size(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        return single(213, str(file_size(session, command.argument)))
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_mdtm(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        return single(213, modified_time(session, command.argument))
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_mkd(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        target = make_directory(session, command.argument)
        return single(257, f'"{virtual_to_text(target)}" created')
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_rmd(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        remove_directory(session, command.argument)
        return single(250, "Requested file action okay, completed")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_dele(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        delete_file(session, command.argument)
        return single(250, "Requested file action okay, completed")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_rnfr(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        rename_from(session, command.argument)
        return single(350, "Requested file action pending further information")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_rnto(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        rename_to(session, command.argument)
        return single(250, "Requested file action okay, completed")
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_type(session: Session, command: Command, logger: logging.Logger) -> Reply:
    selected = command.argument.strip().upper()
    if selected not in {"A", "I"}:
        return SYNTAX_ERROR
    if _transfer_is_active(session):
        return single(450, "A transfer is already in progress")
    session.transfer_type = selected
    return single(200, f"Type set to {selected}")


def _handle_mode(session: Session, command: Command, logger: logging.Logger) -> Reply:
    selected = command.argument.strip().upper()
    if selected == "S":
        session.transfer_mode = selected
        return single(200, "Mode set to S")
    if selected in {"B", "C"}:
        return single(504, "Transfer mode not supported")
    return SYNTAX_ERROR


def _handle_pasv(session: Session, command: Command, logger: logging.Logger) -> Reply:
    if _transfer_is_active(session):
        return single(450, "A transfer is already in progress")
    _reset_data_state(session)
    try:
        udp_socket, endpoint = bind_passive_socket(DEFAULT_HOST)
    except OSError:
        return single(425, "Can't open data connection")
    session.transfer.udp_socket, session.passive_endpoint, session.data_mode = udp_socket, endpoint, "PASSIVE"
    _log(session, logger, f"pasv endpoint={endpoint.host}:{endpoint.port}")
    return single(227, f"Entering Passive Mode {format_passive_reply(endpoint)}")


def _handle_port(session: Session, command: Command, logger: logging.Logger) -> Reply:
    if _transfer_is_active(session):
        return single(450, "A transfer is already in progress")
    try:
        endpoint = parse_port_argument(command.argument, control_peer_host=session.client_address[0])
    except DataChannelError as exc:
        return single(501, str(exc))
    _reset_data_state(session)
    session.active_endpoint, session.data_mode = endpoint, "ACTIVE"
    return single(200, "PORT command successful")


def _handle_hash(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        target = resolve_virtual_path(session, _require_argument(command), required=True, must_exist=True)
        if not target.real.is_file():
            raise FilesystemError("HASH requires a regular file")
        return single(213, sha256_path(target.real))
    except FilesystemError as exc:
        return _safe_reply(exc)


def _handle_abor(session: Session, command: Command, logger: logging.Logger) -> Reply:
    worker = _cancel_transfer(session)
    if worker is None:
        _reset_data_state(session)
        return single(225, "No transfer in progress")
    _log(session, logger, f"transfer abort requested id={session.transfer.transfer_id}")
    return single(226, "Abort successful")


def _prepare_transfer(session: Session, request: TransferRequest, logger: logging.Logger) -> Reply:
    with session.transfer.lock:
        if _transfer_is_active(session):
            return single(450, "A transfer is already in progress")
        if session.data_mode == "PASSIVE":
            udp_socket = session.transfer.udp_socket
            if udp_socket is None:
                return single(425, "Can't open data connection")
        elif session.data_mode == "ACTIVE":
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind((DEFAULT_HOST, 0))
        else:
            return single(425, "Use PASV or PORT before a file transfer")
        transfer_id = new_transfer_id()
        session.transfer.begin(transfer_id, request.direction, udp_socket)
        session.pending_transfer = request
    _log(session, logger, f"transfer prepared id={transfer_id} direction={request.direction} path={request.display_path}")
    return single(150, f"Opening UDP data connection; transfer_id={transfer_id}")


def _handle_retr(session: Session, command: Command, logger: logging.Logger) -> Reply:
    try:
        target = resolve_virtual_path(session, _require_argument(command), required=True, must_exist=True)
        if not target.real.is_file():
            raise FilesystemError("RETR requires a regular file")
    except FilesystemError as exc:
        return _safe_reply(exc)
    return _prepare_transfer(session, TransferRequest("send", source=target.real, display_path=virtual_to_text(target.virtual)), logger)


def _handle_stor_like(session: Session, command: Command, logger: logging.Logger, *, append: bool = False, unique: bool = False) -> Reply:
    try:
        if unique:
            requested = command.argument.strip() or "upload.bin"
            target = resolve_virtual_path(session, requested, required=True, must_exist=False)
            stem, suffix, counter = target.real.stem, target.real.suffix, 1
            while target.real.exists():
                target = resolve_virtual_path(session, f"{stem}-{counter}{suffix}", required=True, must_exist=False)
                counter += 1
        else:
            target = resolve_virtual_path(session, _require_argument(command), required=True, must_exist=False)
        if target.real.exists() and target.real.is_dir():
            raise FilesystemError("Transfer destination is a directory")
        if not target.real.parent.is_dir():
            raise FilesystemError("Destination parent does not exist")
    except FilesystemError as exc:
        return _safe_reply(exc)
    temporary = target.real.with_name(f".{target.real.name}.incoming") if append else target.real
    return _prepare_transfer(
        session,
        TransferRequest("receive", destination=temporary, append_to=target.real if append else None, display_path=virtual_to_text(target.virtual)),
        logger,
    )


def _handle_stor(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return _handle_stor_like(session, command, logger)


def _handle_stou(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return _handle_stor_like(session, command, logger, unique=True)


def _handle_appe(session: Session, command: Command, logger: logging.Logger) -> Reply:
    return _handle_stor_like(session, command, logger, append=True)


def _execute_pending_transfer(session: Session, logger: logging.Logger, context: ServerContext) -> Reply:
    request = session.pending_transfer
    if request is None or session.transfer.transfer_id is None or session.transfer.udp_socket is None:
        return single(451, "Transfer state was unavailable")
    transfer_id, udp_socket = session.transfer.transfer_id, session.transfer.udp_socket
    peer = (session.active_endpoint.host, session.active_endpoint.port) if session.data_mode == "ACTIVE" and session.active_endpoint else None
    try:
        log = lambda message: _log(session, logger, message)
        ascii_mode = session.transfer_type == "A"
        if request.direction == "send":
            result = send_file(udp_socket, peer, request.source, transfer_id, cancel=session.transfer.cancel, log=log, ascii_mode=ascii_mode)
        else:
            result = receive_file(udp_socket, peer, request.destination, transfer_id, cancel=session.transfer.cancel, log=log, ascii_mode=ascii_mode)
            if request.append_to is not None:
                with context.file_lock(request.append_to):
                    with request.append_to.open("ab") as output, request.destination.open("rb") as incoming:
                        output.write(incoming.read())
                    request.destination.unlink(missing_ok=True)
                result_hash = sha256_path(request.append_to)
                session.transfer.bytes_transferred, session.transfer.sha256 = result.bytes_transferred, result_hash
                return single(226, f"Append complete; bytes={result.bytes_transferred}; sha256={result_hash}")
        session.transfer.bytes_transferred, session.transfer.sha256 = result.bytes_transferred, result.sha256
        _log(session, logger, f"transfer complete id={transfer_id} bytes={result.bytes_transferred} sha256={result.sha256} retransmissions={result.retransmissions}")
        return single(226, f"Transfer complete; bytes={result.bytes_transferred}; sha256={result.sha256}")
    except TransferAborted:
        return single(426, "Connection closed; transfer aborted")
    except (TransferError, OSError) as exc:
        return single(426, f"Transfer failed: {exc}")
    finally:
        with session.transfer.lock:
            session.pending_transfer = None
            session.transfer.finish()
            session.data_mode, session.active_endpoint, session.passive_endpoint = "NONE", None, None


DISPATCH = {
    "USER": _handle_user, "PASS": _handle_pass, "NOOP": _handle_noop, "HELP": _handle_help, "QUIT": _handle_quit,
    "PWD": _handle_pwd, "CWD": _handle_cwd, "CDUP": _handle_cdup, "LIST": _handle_list, "NLST": _handle_nlst,
    "SIZE": _handle_size, "MDTM": _handle_mdtm, "MKD": _handle_mkd, "RMD": _handle_rmd, "DELE": _handle_dele,
    "RNFR": _handle_rnfr, "RNTO": _handle_rnto, "TYPE": _handle_type, "MODE": _handle_mode, "PASV": _handle_pasv,
    "PORT": _handle_port, "RETR": _handle_retr, "STOR": _handle_stor, "STOU": _handle_stou, "APPE": _handle_appe,
    "ABOR": _handle_abor, "HASH": _handle_hash,
}


def handle_command(session: Session, command: Command, logger: logging.Logger, context: ServerContext | None = None) -> tuple[Reply, bool]:
    """Handle one parsed control command; transfers are executed after its 150 reply."""

    context = context or ServerContext()
    if context.registry.status_lines() == ["active_sessions=0"]:
        context.registry.add(session)
    _log(session, logger, f"command={sanitize_command_for_log(command)}")
    if (is_filesystem_command(command.verb) or is_data_command(command.verb)) and not session.authenticated:
        return single(530, "Not logged in"), False
    if command.verb == "STAT":
        reply = _handle_stat(session, command, logger, context)
    else:
        handler = DISPATCH.get(command.verb)
        reply = handler(session, command, logger) if handler else single(500, "Unknown command")
    if is_filesystem_command(command.verb):
        _log(session, logger, f"fs command={command.verb} virtual={virtual_to_text(session.cwd)}")
    _log(session, logger, f"reply={reply.code} {reply.lines[-1]}")
    return reply, command.verb == "QUIT"


def _send_reply(conn: socket.socket, reply: Reply, session: Session | None = None) -> bool:
    try:
        if session is None:
            conn.sendall(format_reply(reply))
        else:
            with session.reply_lock:
                conn.sendall(format_reply(reply))
        return True
    except OSError:
        return False


def _run_transfer_worker(conn: socket.socket, session: Session, logger: logging.Logger, context: ServerContext) -> None:
    final = _execute_pending_transfer(session, logger, context)
    _log(session, logger, f"reply={final.code} {final.lines[-1]}")
    _send_reply(conn, final, session)


def _start_transfer_worker(conn: socket.socket, session: Session, logger: logging.Logger, context: ServerContext) -> None:
    worker = threading.Thread(
        target=_run_transfer_worker,
        args=(conn, session, logger, context),
        name=f"hybridftp-transfer-{session.session_id}",
        daemon=True,
    )
    with session.transfer.lock:
        session.transfer.worker = worker
    worker.start()


def _read_control_line(conn: socket.socket, buffer: bytearray) -> bytes | None:
    while b"\n" not in buffer:
        try:
            chunk = conn.recv(1)
        except OSError:
            return None
        if not chunk:
            return bytes(buffer) if buffer else None
        buffer.extend(chunk)
        if len(buffer) > MAX_CONTROL_LINE + 2:
            while chunk and chunk != b"\n":
                try:
                    chunk = conn.recv(1)
                except OSError:
                    break
            raw, buffer[:] = bytes(buffer), b""
            return raw
    index = buffer.index(10) + 1
    raw = bytes(buffer[:index])
    del buffer[:index]
    return raw


def _client_session(conn: socket.socket, address: tuple[str, int], session_id: int, root: Path, logger: logging.Logger, context: ServerContext) -> None:
    session = Session(session_id=session_id, client_address=address, server_root=root)
    context.registry.add(session)
    _log(session, logger, "connect")
    try:
        with conn:
            _send_reply(conn, GREETING)
            buffer = bytearray()
            while True:
                raw = _read_control_line(conn, buffer)
                if raw is None:
                    _log(session, logger, "disconnect without QUIT")
                    break
                try:
                    command = parse_control_line(raw)
                except ParseError:
                    _send_reply(conn, SYNTAX_ERROR)
                    continue
                reply, close_session = handle_command(session, command, logger, context)
                if not _send_reply(conn, reply, session):
                    _log(session, logger, "control connection closed while sending reply")
                    break
                if reply.code == 150 and session.pending_transfer is not None:
                    _start_transfer_worker(conn, session, logger, context)
                if close_session:
                    break
    finally:
        _cancel_and_join_transfer(session)
        context.registry.remove(session.session_id)


def serve(host: str, port: int, root: Path, log_file: Path | None = None, ready_event: threading.Event | None = None, stop_event: threading.Event | None = None, bound_port_queue: queue.Queue[int] | None = None) -> int:
    """Run a multi-client TCP control server; each client owns isolated state."""

    logger = setup_logging(log_file=log_file)
    server_root = resolve_server_root(root)
    stop_event = stop_event or threading.Event()
    context = ServerContext()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.listen(16)
            sock.settimeout(0.2)
            actual_port = sock.getsockname()[1]
            logger.info("server root=%s", server_root)
            logger.info("listening host=%s port=%s", host, actual_port)
            if bound_port_queue:
                bound_port_queue.put(actual_port)
            if ready_event:
                ready_event.set()
            while not stop_event.is_set():
                try:
                    conn, address = sock.accept()
                except socket.timeout:
                    continue
                worker = threading.Thread(target=_client_session, args=(conn, address, context.next_session_id(), server_root, logger, context), daemon=True)
                with context.workers_lock:
                    context.workers.add(worker)
                worker.start()
        with context.workers_lock:
            workers = list(context.workers)
        for worker in workers:
            worker.join(timeout=1.0)
        logger.info("shutdown complete")
        return 0
    except KeyboardInterrupt:
        logger.info("graceful shutdown requested by Ctrl+C")
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
    ready, stop, ports = threading.Event(), threading.Event(), queue.Queue(maxsize=1)
    thread = threading.Thread(target=serve, kwargs={"host": DEFAULT_HOST, "port": 0, "root": root, "log_file": log_file, "ready_event": ready, "stop_event": stop, "bound_port_queue": ports}, daemon=True)
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
    return serve(args.host, args.port, args.root, args.log_file)


if __name__ == "__main__":
    raise SystemExit(main())
