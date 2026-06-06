"""Hybrid FTP Phase 1 TCP control server."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .commands import Command, help_reply, is_protected_placeholder
from .replies import Reply, single
from .session import DEMO_USERS, Session


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hybrid FTP TCP control server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2121)
    parser.add_argument("--root", type=Path, default=Path("server_root"))
    parser.add_argument("--log-file", type=Path, default=None)
    parser.parse_args(argv)
    raise SystemExit("TCP server loop is implemented in the next Phase 1 task")


if __name__ == "__main__":
    raise SystemExit(main())
